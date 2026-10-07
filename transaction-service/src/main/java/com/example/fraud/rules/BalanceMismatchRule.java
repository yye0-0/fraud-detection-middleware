package com.example.fraud.rules;

import com.example.fraud.domain.TransactionRequest;
import java.math.BigDecimal;
import java.util.Optional;
import org.springframework.stereotype.Component;

@Component
public class BalanceMismatchRule implements FraudRule {
    private static final BigDecimal ABSOLUTE_TOLERANCE = new BigDecimal("1.00");
    private static final BigDecimal RELATIVE_TOLERANCE = new BigDecimal("0.05");

    @Override
    public Optional<String> evaluate(TransactionRequest tx) {
        BigDecimal expected = tx.oldbalanceOrg().subtract(tx.amount());
        BigDecimal difference = expected.subtract(tx.newbalanceOrig()).abs();
        BigDecimal tolerance = tx.oldbalanceOrg().multiply(RELATIVE_TOLERANCE).max(ABSOLUTE_TOLERANCE);
        return difference.compareTo(tolerance) > 0 ? Optional.of(code()) : Optional.empty();
    }

    @Override public String code() { return "BALANCE_MISMATCH"; }
}
