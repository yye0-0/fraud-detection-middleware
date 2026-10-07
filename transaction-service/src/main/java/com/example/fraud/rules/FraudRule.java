package com.example.fraud.rules;

import com.example.fraud.domain.TransactionRequest;
import java.util.Optional;

/** Strategy contract for one independently testable fraud signal. */
public interface FraudRule {
    Optional<String> evaluate(TransactionRequest transaction);
    String code();
}
