using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace MyApp.Services;

/// <summary>
/// Service responsible for order management business logic.
/// </summary>
public class OrderService : IOrderService, IAuditable
{
    private readonly IOrderRepository _repository;
    private static readonly string DefaultCurrency = "USD";

    /// <summary>
    /// Gets or sets the maximum number of retries.
    /// </summary>
    public int MaxRetries { get; set; } = 3;

    /// <summary>
    /// Gets the service name.
    /// </summary>
    public string ServiceName { get; init; } = "OrderService";

    public OrderService(IOrderRepository repository)
    {
        _repository = repository;
    }

    /// <summary>
    /// Retrieves an order by ID.
    /// </summary>
    public async Task<OrderDto> GetByIdAsync(Guid id)
    {
        var order = await _repository.FindByIdAsync(id);
        return MapToDto(order);
    }

    /// <summary>
    /// Creates a new order from the request.
    /// </summary>
    public async Task<OrderDto> CreateAsync(CreateOrderRequest request)
    {
        var order = new Order
        {
            Id = Guid.NewGuid(),
            CustomerName = request.CustomerName,
            Status = OrderStatus.Pending
        };
        await _repository.SaveAsync(order);
        return MapToDto(order);
    }

    private OrderDto MapToDto(Order order)
    {
        return new OrderDto { Id = order.Id, CustomerName = order.CustomerName };
    }
}
