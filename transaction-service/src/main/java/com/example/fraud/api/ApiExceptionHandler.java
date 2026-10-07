package com.example.fraud.api;

import java.time.Instant;
import java.util.Map;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<Map<String, Object>> duplicate(DataIntegrityViolationException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(Map.of("timestamp", Instant.now(), "status", 409, "error", "Conflict", "message", "transactionId has already been assessed"));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> validation(MethodArgumentNotValidException ex) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .findFirst().orElse("Request validation failed");
        return ResponseEntity.badRequest().body(Map.of("timestamp", Instant.now(), "status", 400, "error", "Bad Request", "message", detail));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> unexpected(Exception ex) {
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .body(Map.of("timestamp", Instant.now(), "status", 502, "error", "Risk assessment failed", "message", "A required assessment dependency is unavailable"));
    }
}
