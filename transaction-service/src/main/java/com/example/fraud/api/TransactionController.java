package com.example.fraud.api;

import com.example.fraud.domain.FraudAssessment;
import com.example.fraud.domain.TransactionRequest;
import com.example.fraud.service.TransactionAssessmentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/transactions")
public class TransactionController {
    private final TransactionAssessmentService service;
    public TransactionController(TransactionAssessmentService service) { this.service = service; }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public FraudAssessment assess(@Valid @RequestBody TransactionRequest request) {
        return service.assess(request);
    }
}
