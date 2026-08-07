package com.example.controller;

import com.example.model.Order;
import com.example.model.OrderDto;
import com.example.service.OrderService;
import java.util.List;
import java.util.UUID;

/**
 * REST controller for order management operations.
 */
@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @GetMapping("/{id}")
    public Order getOrder(@PathVariable UUID id) {
        return orderService.findById(id);
    }

    @PostMapping
    public Order createOrder(@RequestBody OrderDto dto) {
        return orderService.create(dto);
    }

    @GetMapping
    public List<Order> listOrders() {
        return orderService.findAll();
    }
}
