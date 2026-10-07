package com.example.fraud.service;

import com.example.fraud.domain.TransactionRequest;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class MlRiskClient {
    private final RestClient client;
    private final ObjectMapper objectMapper;

    public MlRiskClient(RestClient.Builder builder, ObjectMapper objectMapper, @Value("${app.ml.base-url}") String baseUrl) {
        this.client = builder.baseUrl(baseUrl).build();
        this.objectMapper = objectMapper;
    }

    public ScoreResult score(TransactionRequest transaction, List<String> ruleSignals) {
        Map<String, Object> body = objectMapper.convertValue(transaction, new TypeReference<>() {});
        body.put("additionalRuleSignals", ruleSignals);
        ScoreResponse response = client.post().uri("/score").body(body).retrieve().body(ScoreResponse.class);
        if (response == null || response.fraudProbability() == null) {
            throw new IllegalStateException("Risk scoring service returned an empty response");
        }
        return new ScoreResult(response.fraudProbability(), response.reviewThreshold(), response.modelVersion(),
                response.reasonCodes() == null ? List.of() : response.reasonCodes());
    }

    public record ScoreResponse(String caseId, String transactionId, String decision, BigDecimal fraudProbability,
                                BigDecimal reviewThreshold, String modelVersion, List<String> reasonCodes, String createdAt) {}
    public record ScoreResult(BigDecimal probability, BigDecimal reviewThreshold, String modelVersion, List<String> signals) {}
}
