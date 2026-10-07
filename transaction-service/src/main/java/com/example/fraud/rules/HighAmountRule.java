package com.example.fraud.rules;

import com.example.fraud.domain.TransactionRequest;
import java.math.BigDecimal;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class HighAmountRule implements FraudRule {
    private static final BigDecimal REVIEW_THRESHOLD = new BigDecimal("200000");

    @Override
    public Optional<String> evaluate(TransactionRequest tx) {
        return tx.amount().compareTo(REVIEW_THRESHOLD) >= 0 ? Optional.of(code()) : Optional.empty();
    }

    @Override public String code() { return "HIGH_AMOUNT"; }
}
