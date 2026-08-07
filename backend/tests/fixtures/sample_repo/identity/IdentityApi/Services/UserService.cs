using System;
using System.Threading.Tasks;
using Xunit;

namespace Acme.Identity.Services
{
    /// <summary>
    /// Loads and persists user accounts.
    /// </summary>
    public class UserService : IUserService
    {
        private readonly IUserRepository _repository;

        public UserService(IUserRepository repository)
        {
            _repository = repository;
        }

        public async Task<User> FindAsync(Guid id)
        {
            var cached = _repository.FromCache(id);
            if (cached != null)
            {
                return cached;
            }
            return await _repository.LoadAsync(id);
        }
    }

    public class UserServiceTests
    {
        [Fact]
        public void FindAsyncReturnsNullForUnknownId()
        {
            var service = new UserService(new FakeRepository());
            Assert.Null(service.FindAsync(Guid.Empty).Result);
        }
    }
}
