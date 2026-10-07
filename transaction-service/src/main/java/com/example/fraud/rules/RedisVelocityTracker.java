package com.example.fraud.rules;

import java.time.Duration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
public class RedisVelocityTracker implements VelocityTracker {
    private static final Duration WINDOW = Duration.ofSeconds(60);
    private final StringRedisTemplate redis;

    public RedisVelocityTracker(StringRedisTemplate redis) { this.redis = redis; }

    @Override
    public long recordAndCount(String accountId) {
        String key = "velocity:account:" + accountId;
        Long count = redis.opsForValue().increment(key);
        if (count != null && count == 1L) redis.expire(key, WINDOW);
        return count == null ? 0L : count;
    }
}
