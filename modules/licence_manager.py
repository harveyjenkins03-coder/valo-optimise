import requests
import hashlib
import hmac
import secrets

# Define the server URL
server_url = 'https://your-licence-server.com'

# Define the secret key for HMAC authentication
secret_key = secrets.token_bytes(32)

# Define the function to validate the licence
def validate_licence(key, machine_id):
    data = {'key': key, 'machine_id': machine_id}
    response = requests.post(server_url + '/validate', json=data)
    return response.json()

# Define the function to activate the licence
def activate_licence(key, machine_id):
    data = {'key': key, 'machine_id': machine_id}
    response = requests.post(server_url + '/activate', json=data)
    return response.json()

# Define the function to check the server health
def check_server_health():
    response = requests.get(server_url + '/health')
    return response.json()
