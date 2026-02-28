#!/usr/bin/env python3
"""
GCP LLM Configuration and Test Script

Helps you configure and test ShopMindAI's connection to your GCP LLM server.

Usage:
    python setup_gcp_llm.py --ip YOUR_GCP_VM_IP
    python setup_gcp_llm.py --test
    python setup_gcp_llm.py --interactive
"""
import os
import sys
import argparse
import json
import requests
from pathlib import Path
from typing import Optional, Tuple


def find_env_file() -> Path:
    """Find or create .env file."""
    env_path = Path(".env")
    if not env_path.exists():
        env_example = Path(".env.example")
        if env_example.exists():
            print(f"✓ Creating .env from .env.example")
            env_path.write_text(env_example.read_text())
        else:
            print(f"✗ No .env or .env.example found")
            return None
    return env_path


def load_env_vars() -> dict:
    """Load environment variables from .env file."""
    env_path = find_env_file()
    if not env_path:
        return {}
    
    env_vars = {}
    for line in env_path.read_text().split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()
    
    return env_vars


def save_env_vars(env_vars: dict) -> bool:
    """Save environment variables to .env file."""
    env_path = find_env_file()
    if not env_path:
        return False
    
    content = env_path.read_text()
    
    for key, value in env_vars.items():
        # Replace existing or add new
        import re
        pattern = f'^{key}=.*$'
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f'{key}={value}', content, flags=re.MULTILINE)
        else:
            content += f'\n{key}={value}'
    
    env_path.write_text(content)
    return True


def test_llm_health(gcp_model_url: str) -> Tuple[bool, str]:
    """Test health endpoint of GCP LLM server."""
    if not gcp_model_url:
        return False, "GCP_MODEL_URL not configured"
    
    # Extract base URL (remove /generate if present)
    base_url = gcp_model_url.replace('/generate', '')
    health_url = f"{base_url}/health"
    
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            return True, f"✓ Health check passed: {response.text[:100]}"
        else:
            return False, f"✗ Health check failed: {response.status_code}"
    except requests.exceptions.Timeout:
        return False, f"✗ Health check timed out (5s)"
    except requests.exceptions.ConnectionError as e:
        return False, f"✗ Connection error: {str(e)}"
    except Exception as e:
        return False, f"✗ Unexpected error: {str(e)}"


def test_llm_generation(gcp_model_url: str) -> Tuple[bool, str]:
    """Test generation endpoint of GCP LLM server."""
    if not gcp_model_url:
        return False, "GCP_MODEL_URL not configured"
    
    test_prompt = "What is the capital of France?"
    
    try:
        response = requests.post(
            gcp_model_url,
            json={"prompt": test_prompt},
            timeout=30
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if "response" in data:
                    result = data["response"][:100]
                    return True, f"✓ Generation successful: {result}..."
                else:
                    return False, f"✗ Missing 'response' field in JSON: {data}"
            except json.JSONDecodeError:
                return False, f"✗ Invalid JSON response: {response.text[:100]}"
        else:
            return False, f"✗ Generation failed: {response.status_code}"
    
    except requests.exceptions.Timeout:
        return False, f"✗ Generation timed out (30s)"
    except requests.exceptions.ConnectionError as e:
        return False, f"✗ Connection error: {str(e)}"
    except Exception as e:
        return False, f"✗ Unexpected error: {str(e)}"


def interactive_setup() -> Optional[str]:
    """Interactive setup wizard."""
    print("\n" + "="*60)
    print("GCP LLM Configuration Wizard")
    print("="*60 + "\n")
    
    print("Enter your GCP LLM server details:\n")
    
    gcp_ip = input("GCP VM External IP (or hostname): ").strip()
    if not gcp_ip:
        print("✗ IP address is required")
        return None
    
    gcp_port = input("LLM Server Port [9000]: ").strip() or "9000"
    
    gcp_model_url = f"http://{gcp_ip}:{gcp_port}/generate"
    print(f"\nConfigured URL: {gcp_model_url}")
    
    # Test connection
    print("\nTesting connection...")
    health_ok, health_msg = test_llm_health(gcp_model_url)
    print(f"  Health: {health_msg}")
    
    if health_ok:
        print("  Testing generation...")
        gen_ok, gen_msg = test_llm_generation(gcp_model_url)
        print(f"  Generation: {gen_msg}")
        
        if gen_ok:
            confirm = input("\n✓ Connection successful! Save to .env? (y/n): ").strip().lower()
            if confirm == 'y':
                env_vars = {
                    'DEFAULT_PROVIDER': 'gcp',
                    'GCP_MODEL_URL': gcp_model_url
                }
                if save_env_vars(env_vars):
                    print("✓ Configuration saved to .env")
                    return gcp_model_url
            return gcp_model_url
    else:
        print("\n✗ Connection failed. Please check:")
        print("  1. GCP VM is running")
        print("  2. LLM server is running on the VM")
        print("  3. Firewall allows port 9000")
        print("  4. IP address is correct")
        return None


def auto_setup(gcp_ip: str) -> Optional[str]:
    """Automatic setup with given IP."""
    gcp_model_url = f"http://{gcp_ip}:9000/generate"
    
    print(f"\nConfiguring: {gcp_model_url}")
    
    # Test connection
    health_ok, health_msg = test_llm_health(gcp_model_url)
    print(f"  {health_msg}")
    
    if health_ok:
        gen_ok, gen_msg = test_llm_generation(gcp_model_url)
        print(f"  {gen_msg}")
        
        if gen_ok:
            env_vars = {
                'DEFAULT_PROVIDER': 'gcp',
                'GCP_MODEL_URL': gcp_model_url
            }
            if save_env_vars(env_vars):
                print(f"\n✓ Configuration saved to .env")
            return gcp_model_url
    
    return None


def test_current_config() -> bool:
    """Test current .env configuration."""
    env_vars = load_env_vars()
    gcp_model_url = env_vars.get('GCP_MODEL_URL')
    
    if not gcp_model_url:
        print("✗ GCP_MODEL_URL not configured in .env")
        return False
    
    print(f"Testing: {gcp_model_url}\n")
    
    # Test health
    health_ok, health_msg = test_llm_health(gcp_model_url)
    print(f"Health: {health_msg}")
    if not health_ok:
        return False
    
    # Test generation
    gen_ok, gen_msg = test_llm_generation(gcp_model_url)
    print(f"Generation: {gen_msg}")
    
    if health_ok and gen_ok:
        print("\n✓ All tests passed!")
        return True
    else:
        print("\n✗ Some tests failed. Check configuration.")
        return False


def show_status() -> None:
    """Show current configuration status."""
    env_vars = load_env_vars()
    
    print("\n" + "="*60)
    print("Current GCP LLM Configuration")
    print("="*60 + "\n")
    
    print(f"DEFAULT_PROVIDER: {env_vars.get('DEFAULT_PROVIDER', 'NOT SET')}")
    print(f"GCP_MODEL_URL: {env_vars.get('GCP_MODEL_URL', 'NOT SET')}")
    
    gcp_model_url = env_vars.get('GCP_MODEL_URL')
    if gcp_model_url:
        print(f"\nTesting connection...")
        health_ok, health_msg = test_llm_health(gcp_model_url)
        print(f"  Health: {health_msg}")


def main():
    parser = argparse.ArgumentParser(
        description="Configure ShopMindAI for GCP LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive setup
  python setup_gcp_llm.py --interactive
  
  # Quick setup with IP
  python setup_gcp_llm.py --ip 35.192.1.2
  
  # Test current configuration
  python setup_gcp_llm.py --test
  
  # Show status
  python setup_gcp_llm.py --status
        """
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Interactive configuration wizard')
    parser.add_argument('--ip', type=str,
                       help='GCP VM IP address')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Test current configuration')
    parser.add_argument('--status', '-s', action='store_true',
                       help='Show current status')
    
    args = parser.parse_args()
    
    # If no args, show status
    if not any(vars(args).values()):
        show_status()
        return
    
    # Handle each option
    if args.interactive:
        interactive_setup()
    elif args.ip:
        auto_setup(args.ip)
    elif args.test:
        test_current_config()
    elif args.status:
        show_status()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗ Cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)
