package com.example.auth;

import com.example.model.User;
import com.example.repository.UserRepository;
import com.example.security.PasswordEncoder;
import java.util.Optional;
import java.util.List;

/**
 * Service responsible for user authentication and management.
 * Handles login, registration, and JWT token generation.
 */
@Service
@Transactional(readOnly = false)
public class UserService implements AuthProvider, Auditable {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private static final String DEFAULT_ROLE = "USER";

    @Autowired
    public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    /**
     * Authenticates user credentials against the repository
     * and returns a JWT token.
     *
     * @param username the user's login name
     * @param password the user's password
     * @return JWT token string
     * @throws AuthenticationException if credentials are invalid
     */
    @Transactional
    public String authenticate(String username, String password) throws AuthenticationException {
        Optional<User> user = userRepository.findByUsername(username);
        if (user.isEmpty()) {
            throw new AuthenticationException("User not found");
        }
        if (!passwordEncoder.matches(password, user.get().getPasswordHash())) {
            throw new AuthenticationException("Invalid password");
        }
        return generateToken(user.get());
    }

    /**
     * Registers a new user in the system.
     */
    public User registerUser(String username, String email, String password) {
        User user = new User();
        user.setUsername(username);
        user.setEmail(email);
        user.setPasswordHash(passwordEncoder.encode(password));
        user.setRole(DEFAULT_ROLE);
        return userRepository.save(user);
    }

    private String generateToken(User user) {
        return "token:" + user.getId();
    }
}
