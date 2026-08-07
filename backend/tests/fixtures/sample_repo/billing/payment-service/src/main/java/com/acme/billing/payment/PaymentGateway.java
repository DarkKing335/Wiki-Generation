package com.acme.billing.payment;

import java.util.List;

/**
 * Contract every payment backend must satisfy.
 */
public interface PaymentGateway {

    PaymentResult charge(TransactionDto dto) throws PaymentException;

    List<PaymentResult> chargeAll(List<TransactionDto> transactions) throws PaymentException;
}
