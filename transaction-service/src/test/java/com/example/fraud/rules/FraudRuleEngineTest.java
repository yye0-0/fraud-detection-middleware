package com.example.fraud.rules;

import static org.junit.jupiter.api.Assertions.assertEquals;
import com.example.fraud.domain.TransactionRequest;
import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class FraudRuleEngineTest {
    @Test void evaluatesRegisteredStrategiesPolymorphically() {
        FraudRule highAmount = new FraudRule() {
            public Optional<String> evaluate(TransactionRequest tx) { return Optional.of("HIGH_AMOUNT"); }
            public String code() { return "HIGH_AMOUNT"; }
        };
        FraudRule none = new FraudRule() {
            public Optional<String> evaluate(TransactionRequest tx) { return Optional.empty(); }
            public String code() { return "NOOP"; }
        };
        FraudRuleEngine engine = new FraudRuleEngine(List.of(highAmount, none));
        TransactionRequest request = new TransactionRequest("tx", "acct", 10, "PAYMENT", BigDecimal.TEN, "SGD",
                new BigDecimal("100"), new BigDecimal("90"), BigDecimal.ZERO, BigDecimal.ZERO);
        assertEquals(List.of("HIGH_AMOUNT"), engine.evaluate(request));
    }
}
