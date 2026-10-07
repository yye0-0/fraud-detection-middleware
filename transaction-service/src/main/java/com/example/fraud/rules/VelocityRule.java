package com.example.fraud.rules;

import com.example.fraud.domain.TransactionRequest;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class VelocityRule implements FraudRule {
    private static final long REVIEW_COUNT = 5;
    private final VelocityTracker tracker;

    public VelocityRule(VelocityTracker tracker) { this.tracker = tracker; }

    @Override
    public Optional<String> evaluate(TransactionRequest tx) {
        return tracker.recordAndCount(tx.accountId()) > REVIEW_COUNT ? Optional.of(code()) : Optional.empty();
    }

    @Override public String code() { return "HIGH_VELOCITY"; }
}
