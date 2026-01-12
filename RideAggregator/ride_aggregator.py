import os
import json
import pika
from datetime import datetime

from repositories import RideAggregatorRepository

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
DB_URL = os.getenv("DB_URL", "postgresql://postgres:yesyes123@localhost:5432/Wihwin")

MAX_RETRIES = 3


def process_ride(ride_id: str, end_time_from_msg: datetime = None) -> str:
    print(f"Processing ride_id={ride_id}")
    ride = RideAggregatorRepository.get_ride_by_id(ride_id)
    if not ride:
        print(f"[WARN] ride_id={ride_id} not found, discarding")
        return 'success'
    
    if ride['status'] == 'completed':
        print(f"ride_id={ride_id} already completed")
        return 'success'
    
    if ride['status'] != 'ending':
        print(f"[WARN] ride_id={ride_id} has invalid status={ride['status']}, discarding")
        return 'invalid_state'
    
  
    if end_time_from_msg:
        end_time = end_time_from_msg
    elif ride['end_time']:
        end_time = ride['end_time']
    else:
        end_time = datetime.now()
    
    start_time = ride['start_time']
    duration_seconds = int((end_time - start_time).total_seconds())
    
 
    stats = RideAggregatorRepository.get_ride_stats(ride_id)
    avg_hr = float(stats['avg_hr']) if stats and stats['avg_hr'] else None
    max_hr = float(stats['max_hr']) if stats and stats['max_hr'] else None
    min_hr = float(stats['min_hr']) if stats and stats['min_hr'] else None
    

    event_stats = RideAggregatorRepository.get_drowsiness_event_stats(ride_id)
    total_drowsiness = event_stats['total_drowsiness_events']
    total_microsleep = event_stats['total_microsleep_events']
    max_score = event_stats['max_drowsiness_score']
    avg_score = float(event_stats['avg_drowsiness_score']) if event_stats['avg_drowsiness_score'] else None
    

    fatigue_score = min(100, int((total_drowsiness * 10) + (total_microsleep * 20)))
    

    result = RideAggregatorRepository.complete_ride_with_summary(
        ride_id=ride_id,
        end_time=end_time,
        duration_seconds=duration_seconds,
        avg_hr=avg_hr,
        max_hr=max_hr,
        min_hr=min_hr,
        fatigue_score=fatigue_score,
        total_drowsiness=total_drowsiness,
        total_microsleep=total_microsleep,
        max_score=max_score,
        avg_score=avg_score
    )
    
    if result is True:
        print(f"[AGGREGATOR] [INFO] ride_id={ride_id} completed - duration={duration_seconds}s fatigue={fatigue_score}/100 avg_hr={avg_hr}")
        return 'success'
    elif result is None:
        print(f"[AGGREGATOR] [WARN] ride_id={ride_id} invalid state during completion, discarding")
        return 'invalid_state'
    else:
        print(f"[AGGREGATOR] [ERROR] ride_id={ride_id} completion failed")
        return 'error'


def get_retry_count(properties) -> int:
    if properties.headers and 'x-retry-count' in properties.headers:
        return properties.headers['x-retry-count']
    return 0


def on_message(ch, method, properties, body):
    ride_id = None
    try:
        msg = json.loads(body)
        ride_id = msg.get('ride_id')
        end_time_str = msg.get('end_time')
        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None
        
        if not ride_id:
            print("[AGGREGATOR] [ERROR] Message missing ride_id, discarding")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        result = process_ride(ride_id, end_time)
        
        if result == 'success':
            ch.basic_ack(delivery_tag=method.delivery_tag)
        elif result == 'invalid_state':
            print(f"[AGGREGATOR] [WARN] ride_id={ride_id} invalid state, acknowledging to prevent infinite loop")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            retry_count = get_retry_count(properties)
            if retry_count >= MAX_RETRIES:
                print(f"[AGGREGATOR] [ERROR] ride_id={ride_id} max retries ({MAX_RETRIES}) exceeded, discarding")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                print(f"[AGGREGATOR] [WARN] ride_id={ride_id} requeuing (retry {retry_count + 1}/{MAX_RETRIES})")
                new_headers = {'x-retry-count': retry_count + 1}
                ch.basic_publish(
                    exchange='',
                    routing_key='ride.end',
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        headers=new_headers
                    )
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            
    except json.JSONDecodeError as e:
        print(f"[AGGREGATOR] [ERROR] Invalid JSON: {e}, discarding")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"[AGGREGATOR] [ERROR] ride_id={ride_id} processing failed: {e}")
        retry_count = get_retry_count(properties)
        if retry_count >= MAX_RETRIES:
            print(f"[AGGREGATOR] [ERROR] ride_id={ride_id} max retries exceeded after exception, discarding")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            print(f"[AGGREGATOR] [WARN] ride_id={ride_id} requeuing after exception (retry {retry_count + 1}/{MAX_RETRIES})")
            new_headers = {'x-retry-count': retry_count + 1}
            ch.basic_publish(
                exchange='',
                routing_key='ride.end',
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers=new_headers
                )
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    print("[AGGREGATOR] [INFO] Starting Ride Aggregator Worker")
    print(f"[AGGREGATOR] [INFO] RabbitMQ: {RABBITMQ_URL}")
    print(f"[AGGREGATOR] [INFO] DB: {DB_URL[:50]}...")
    print(f"[AGGREGATOR] [INFO] Max retries: {MAX_RETRIES}")
    
    RideAggregatorRepository.init_pool(DB_URL)
    
    params = pika.URLParameters(RABBITMQ_URL)
    connection = None
    
    for attempt in range(10):
        try:
            connection = pika.BlockingConnection(params)
            break
        except pika.exceptions.AMQPConnectionError as e:
            print(f"[AGGREGATOR] [WARN] Connection attempt {attempt + 1}/10 failed: {e}")
            import time
            time.sleep(5)
    
    if not connection:
        print("[AGGREGATOR] [ERROR] Failed to connect to RabbitMQ after 10 attempts")
        return
    
    channel = connection.channel()
    channel.queue_declare(queue='ride.end', durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='ride.end', on_message_callback=on_message)
    
    print("[AGGREGATOR] [INFO] Connected to RabbitMQ, consuming from queue=ride.end")
    
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("\n[AGGREGATOR] [INFO] Shutting down...")
        channel.stop_consuming()
    finally:
        connection.close()
        RideAggregatorRepository.close_pool()
        print("[AGGREGATOR] [INFO] Shutdown complete")


if __name__ == "__main__":
    main()
