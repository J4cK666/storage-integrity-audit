from audit_algorithm.public_parameter import PP

def save_user_info(PP):
    # This function saves user information to the database
    user_info = {}
    user_info['account_id'] = '1234567890'  # Example account ID
    user_info['username'] = 'example_user'  # Example username
    user_info['password'] = 'example_password'  # Example password (should be hashed in production)
    user_info['public_key'] = PP['pk']
    user_info['private_key'] = PP['sk']
    
    
    return user_info 