using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace MyApp.Services;

/// <summary>
/// Interface for order management operations.
/// </summary>
public interface IOrderService
{
    Task<OrderDto> GetByIdAsync(Guid id);

    Task<OrderDto> CreateAsync(CreateOrderRequest request);

    Task<List<OrderDto>> ListAsync(int page);
}
