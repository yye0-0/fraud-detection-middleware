package com.example.fraud.domain;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

public record TransactionRequest(
        @NotBlank @Size(max = 100) String transactionId,
        @NotBlank @Size(max = 100) String accountId,
        @NotNull @Min(1) Integer step,
        @NotBlank @Size(max = 40) String type,
        @NotNull @DecimalMin("0.0") BigDecimal amount,
        @NotBlank @Size(max = 3) String currency,
        @NotNull @DecimalMin("0.0") BigDecimal oldbalanceOrg,
        @NotNull @DecimalMin("0.0") BigDecimal newbalanceOrig,
        @NotNull @DecimalMin("0.0") BigDecimal oldbalanceDest,
        @NotNull @DecimalMin("0.0") BigDecimal newbalanceDest
) {}
