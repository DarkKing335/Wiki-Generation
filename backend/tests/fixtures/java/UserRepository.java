package com.example.repository;

import com.example.model.User;
import java.util.Optional;

/**
 * Repository interface for User entity persistence.
 */
public interface UserRepository extends CrudRepository<User, Long> {

    Optional<User> findByUsername(String username);

    Optional<User> findByEmail(String email);
}
