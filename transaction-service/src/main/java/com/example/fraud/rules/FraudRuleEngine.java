package com.example.fraud.rules;

import com.example.fraud.domain.TransactionRequest;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class FraudRuleEngine {
    private final List<FraudRule> rules;

    public FraudRuleEngine(List<FraudRule> rules) { this.rules = List.copyOf(rules); }

    public List<String> evaluate(TransactionRequest transaction) {
        return rules.stream()
                .map(rule -> rule.evaluate(transaction))
                .flatMap(java.util.Optional::stream)
                .toList();
    }
}
