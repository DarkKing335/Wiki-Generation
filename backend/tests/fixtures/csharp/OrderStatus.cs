namespace MyApp.Models;

/// <summary>
/// Represents the status of an order.
/// </summary>
public enum OrderStatus
{
    Pending,
    Confirmed,
    Shipped,
    Delivered,
    Cancelled
}
