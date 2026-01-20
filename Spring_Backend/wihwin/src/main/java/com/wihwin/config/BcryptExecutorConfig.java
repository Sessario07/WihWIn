package com.wihwin.config;

import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class BcryptExecutorConfig {
    
    @Bean("bcryptExecutor")
    public Executor bcryptExecutor() {
        int cores = Runtime.getRuntime().availableProcessors();
        return Executors.newFixedThreadPool(
            cores,
            r -> {
                Thread t = new Thread(r);
                t.setName("bcrypt-worker");
                t.setDaemon(true);
                return t;
            }
        );
    }

}
