#!/usr/bin/env python3
"""Test script to verify database connection using psycopg2 (direct and via SQLAlchemy)."""
import psycopg2
from dotenv import load_dotenv
import os
from config import settings
from database import engine, SessionLocal
from sqlalchemy import text
import sys
import socket
import urllib.request
import json

# Load environment variables from .env
load_dotenv()


def get_public_ip():
    """Get the current public IP address of this machine."""
    print("\n" + "=" * 60)
    print("PUBLIC IP ADDRESS DETECTION")
    print("=" * 60)
    
    ip_services = [
        ("ipify.org", "https://api.ipify.org?format=json"),
        ("icanhazip.com", "https://icanhazip.com"),
        ("ifconfig.me", "https://ifconfig.me/ip"),
    ]
    
    for service_name, url in ip_services:
        try:
            print(f"\nTrying {service_name}...")
            with urllib.request.urlopen(url, timeout=5) as response:
                if "json" in url:
                    data = json.loads(response.read().decode())
                    ip = data.get("ip", "")
                else:
                    ip = response.read().decode().strip()
                
                if ip:
                    print(f"✓ Your current public IP address: {ip}")
                    return ip
        except Exception as e:
            print(f"  ✗ Failed: {type(e).__name__}")
            continue
    
    print("\n✗ Could not determine public IP address")
    return None


def check_ip_whitelist_status(whitelisted_ip, current_ip):
    """Check if the current IP matches the whitelisted IP."""
    print("\n" + "=" * 60)
    print("IP WHITELIST ANALYSIS")
    print("=" * 60)
    
    print(f"\nWhitelisted IP/CIDR: {whitelisted_ip}")
    print(f"Your current public IP: {current_ip}")
    
    if not current_ip:
        print("\n⚠ Cannot verify IP match - could not detect your public IP")
        return False
    
    # Parse CIDR notation (e.g., 51.155.208.33/32)
    if "/" in whitelisted_ip:
        ip_part, cidr = whitelisted_ip.split("/")
        cidr = int(cidr)
    else:
        ip_part = whitelisted_ip
        cidr = 32  # Single IP
    
    # Check if IPs match
    if ip_part == current_ip:
        print(f"\n✓ IP MATCH! Your IP ({current_ip}) matches the whitelisted IP")
        print(f"\n⚠ IMPORTANT NOTES:")
        print(f"  1. If connection still fails, Supabase may need a few minutes")
        print(f"     to propagate the IP whitelist changes (usually 1-5 minutes)")
        print(f"  2. Try waiting a few minutes and test again")
        print(f"  3. Make sure you clicked 'Save' in Supabase dashboard")
        print(f"  4. Check if there are multiple IP restrictions that might conflict")
        return True
    else:
        print(f"\n✗ IP MISMATCH!")
        print(f"  Whitelisted: {ip_part}")
        print(f"  Your current IP: {current_ip}")
        print(f"\n⚠ This is likely why the connection fails when IP is restricted!")
        print(f"  Your IP may have changed, or you're behind a NAT/proxy")
        print(f"\n  SOLUTION: Update Supabase whitelist to include: {current_ip}/32")
        return False


def test_network_connectivity(host, port):
    """Test basic network connectivity to the database host."""
    print("\n" + "=" * 60)
    print("NETWORK CONNECTIVITY CHECK")
    print("=" * 60)
    
    # Try IPv4 first
    try:
        print(f"\nTesting IPv4 connectivity to {host}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        
        if result == 0:
            print(f"✓ IPv4 connectivity OK - port {port} is reachable")
            return True
        else:
            print(f"  ✗ IPv4 connection failed (result code: {result})")
    except socket.gaierror as e:
        print(f"  ✗ IPv4 DNS resolution failed: {e}")
    except Exception as e:
        print(f"  ✗ IPv4 test error: {type(e).__name__}: {e}")
    
    # Try IPv6 if IPv4 failed
    try:
        print(f"\nTesting IPv6 connectivity to {host}:{port}...")
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        
        if result == 0:
            print(f"✓ IPv6 connectivity OK - port {port} is reachable")
            return True
        else:
            print(f"  ✗ IPv6 connection failed (result code: {result})")
    except socket.gaierror as e:
        print(f"  ✗ IPv6 DNS resolution failed: {e}")
    except Exception as e:
        print(f"  ✗ IPv6 test error: {type(e).__name__}: {e}")
    
    print(f"\n⚠ Network connectivity test failed for both IPv4 and IPv6")
    print("  Note: This test may fail even if database connection works")
    print("  (psycopg2 handles DNS resolution differently)")
    return False

def test_direct_psycopg2_connection():
    """Test direct psycopg2 connection using explicit format (like user's example)."""
    print("=" * 60)
    print("TEST 1: Direct psycopg2 Connection")
    print("=" * 60)
    
    # Fetch variables from environment (matching user's example format)
    USER = os.getenv("user") or os.getenv("DB_USER")
    PASSWORD = os.getenv("password") or os.getenv("DB_PASSWORD")
    HOST = os.getenv("host") or os.getenv("DB_HOST")
    PORT = os.getenv("port") or os.getenv("DB_PORT") or "5432"
    DBNAME = os.getenv("dbname") or os.getenv("DB_NAME")
    
    print(f"\nConnection Parameters:")
    print(f"  User: {USER}")
    print(f"  Host: {HOST}")
    print(f"  Port: {PORT}")
    print(f"  Database: {DBNAME}")
    print(f"  Password: {'*' * len(PASSWORD) if PASSWORD else 'NOT SET'}")
    
    if not all([USER, PASSWORD, HOST, DBNAME]):
        print("\n✗ ERROR: Missing required connection parameters!")
        print("  Required: user, password, host, dbname")
        return False
    
    # Try multiple connection methods
    is_supabase = "supabase.co" in HOST or "supabase.com" in HOST
    
    connection_configs = []
    
    if is_supabase:
        # For Supabase, try different SSL configurations
        connection_configs = [
            ("SSL mode: require", {"sslmode": "require"}),
            ("SSL mode: prefer", {"sslmode": "prefer"}),
            ("SSL mode: allow", {"sslmode": "allow"}),
        ]
        
        # Also try connection pooling port (6543) if using default port
        if PORT == "5432":
            connection_configs.append(("Connection Pooling Port (6543) with SSL", {
                "port": "6543",
                "sslmode": "require"
            }))
    else:
        # For regular PostgreSQL, try without SSL first
        connection_configs = [
            ("No SSL", {}),
            ("SSL mode: prefer", {"sslmode": "prefer"}),
        ]
    
    # Track detailed error information
    last_error = None
    timeout_count = 0
    
    # Connect to the database
    for config_name, ssl_config in connection_configs:
        try:
            print(f"\nAttempting connection: {config_name}...")
            
            # Store port before popping
            test_port = ssl_config.pop("port", PORT) if "port" in ssl_config else PORT
            
            connect_params = {
                "user": USER,
                "password": PASSWORD,
                "host": HOST,
                "port": test_port,
                "dbname": DBNAME,
                "connect_timeout": 10
            }
            connect_params.update(ssl_config)
            
            connection = psycopg2.connect(**connect_params)
            print(f"✓ Connection successful with {config_name}!")
            
            # Create a cursor to execute SQL queries
            cursor = connection.cursor()
            
            # Try to get connection info (what IP Supabase sees)
            try:
                # PostgreSQL doesn't directly show client IP, but we can try
                cursor.execute("SELECT inet_server_addr(), inet_client_addr();")
                server_info = cursor.fetchone()
                if server_info and server_info[1]:
                    print(f"  Note: Server sees client IP as: {server_info[1]}")
            except:
                pass  # This query might not work on all PostgreSQL versions
            
            # Example query - get current time
            cursor.execute("SELECT NOW();")
            result = cursor.fetchone()
            print(f"✓ Query successful! Current Time: {result[0]}")
            
            # Test PostgreSQL version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✓ PostgreSQL Version: {version[0][:50]}...")
            
            # Test database name
            cursor.execute("SELECT current_database();")
            db_name = cursor.fetchone()
            print(f"✓ Connected to database: {db_name[0]}")
            
            # Close the cursor and connection
            cursor.close()
            connection.close()
            print("✓ Connection closed properly.")
            
            return True
            
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            last_error = error_msg
            
            # Check for specific error types
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                timeout_count += 1
                print(f"  ✗ Timeout (attempt {timeout_count}/{len(connection_configs)})")
                
                # If all attempts timeout, provide specific guidance
                if timeout_count == len(connection_configs):
                    print(f"\n  ⚠ ALL CONNECTION ATTEMPTS TIMED OUT")
                    print(f"  This strongly suggests an IP whitelist or firewall issue")
            elif "connection refused" in error_msg.lower():
                print(f"  ✗ Connection refused - server may be down or port blocked")
            elif "authentication failed" in error_msg.lower():
                print(f"  ✗ Authentication failed - check credentials")
            elif "no route to host" in error_msg.lower():
                print(f"  ✗ No route to host - network/firewall issue")
            else:
                print(f"  ✗ Failed: {error_msg[:150]}")
            continue
        except psycopg2.ProgrammingError as e:
            print(f"  ✗ Database error: {e}")
            last_error = str(e)
            continue
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}: {str(e)[:150]}")
            last_error = str(e)
            continue
    
    # If all methods failed, provide detailed analysis
    print(f"\n✗ All connection attempts failed!")
    
    if timeout_count == len(connection_configs):
        print("\n" + "=" * 60)
        print("TIMEOUT ANALYSIS - IP WHITELIST ISSUE LIKELY")
        print("=" * 60)
        print("\nAll connections timed out, which typically indicates:")
        print("  1. 🔒 IP WHITELIST BLOCKING (MOST LIKELY)")
        print("     - Your IP might not be properly whitelisted")
        print("     - Supabase might see a different IP than detected")
        print("     - There might be a delay in whitelist propagation")
        print("\n  2. 🔍 VERIFICATION STEPS:")
        print("     a. In Supabase Dashboard → Settings → Database:")
        print("        - Check Network Restrictions section")
        print("        - Verify IP format: 51.155.208.33/32 (with /32)")
        print("        - Make sure 'Restrict all access' is NOT enabled")
        print("        - Try removing and re-adding the IP")
        print("     b. Test with 'Allow all access' to confirm connection works")
        print("     c. Check Supabase logs for connection attempts")
        print("\n  3. 🌐 POSSIBLE IP MISMATCH:")
        print("     - Your router/VPN might be changing the source IP")
        print("     - Multiple network interfaces might be in use")
        print("     - ISP might be using carrier-grade NAT")
        print("\n  4. 💡 WORKAROUNDS:")
        print("     - Use 'Allow all access' for development")
        print("     - Add a broader IP range (e.g., /24 instead of /32)")
        print("     - Check if you're behind a corporate proxy/VPN")
    
    print("\nGeneral troubleshooting tips:")
    print("  - Verify host, port, and database name are correct")
    print("  - Check firewall/network settings")
    print("  - For Supabase: Try connection pooling port (6543)")
    print("  - Try connecting from a different network/VPN")
    
    if last_error:
        print(f"\nLast error details: {last_error[:200]}")
    
    return False


def test_sqlalchemy_connection():
    """Test SQLAlchemy connection (what the app actually uses)."""
    print("\n" + "=" * 60)
    print("TEST 2: SQLAlchemy Connection (via database.py)")
    print("=" * 60)
    
    try:
        print("\nTesting SQLAlchemy engine connection...")
        
        # Test engine connection
        with engine.connect() as conn:
            print("✓ Engine connection successful!")
            
            # Test a simple query
            result = conn.execute(text("SELECT NOW();"))
            current_time = result.fetchone()[0]
            print(f"✓ Query successful! Current Time: {current_time}")
            
            # Test PostgreSQL version
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✓ PostgreSQL Version: {version[:50]}...")
            
            # Test database name
            result = conn.execute(text("SELECT current_database();"))
            db_name = result.fetchone()[0]
            print(f"✓ Connected to database: {db_name}")
        
        # Test session factory
        print("\nTesting SQLAlchemy session...")
        db = SessionLocal()
        try:
            result = db.execute(text("SELECT NOW();"))
            current_time = result.fetchone()[0]
            print(f"✓ Session query successful! Current Time: {current_time}")
        finally:
            db.close()
            print("✓ Session closed properly.")
        
        return True
        
    except Exception as e:
        print(f"\n✗ SQLAlchemy connection failed: {type(e).__name__}: {e}")
        return False


def test_database_tables():
    """Test if we can query database tables."""
    print("\n" + "=" * 60)
    print("TEST 3: Database Tables Check")
    print("=" * 60)
    
    try:
        db = SessionLocal()
        try:
            # Check if tables exist
            result = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            
            if tables:
                print(f"\n✓ Found {len(tables)} table(s) in database:")
                for table in tables:
                    print(f"  - {table}")
            else:
                print("\n⚠ No tables found in database (this is OK if database is new)")
            
            return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"\n✗ Error checking tables: {type(e).__name__}: {e}")
        return False


def main():
    """Run all connection tests."""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION TEST SUITE")
    print("=" * 60)
    
    # Get connection parameters for network test
    HOST = os.getenv("host") or os.getenv("DB_HOST")
    PORT = os.getenv("port") or os.getenv("DB_PORT") or "5432"
    
    results = []
    
    # Get public IP address
    current_ip = get_public_ip()
    
    # Check IP whitelist if user provided one
    whitelisted_ip = os.getenv("WHITELISTED_IP") or "51.155.208.33/32"  # Default from user's example
    if whitelisted_ip and current_ip:
        ip_match = check_ip_whitelist_status(whitelisted_ip, current_ip)
        results.append(("IP Whitelist Match", ip_match))
    
    # Network connectivity check
    if HOST:
        network_ok = test_network_connectivity(HOST, PORT)
        results.append(("Network Connectivity", network_ok))
        
        if not network_ok:
            print("\n⚠ NOTE: Network connectivity test failed, but this is often a false negative.")
            print("  The actual database connection test below is more reliable.")
    
    # Test 1: Direct psycopg2 connection
    direct_conn_result = test_direct_psycopg2_connection()
    results.append(("Direct psycopg2", direct_conn_result))
    
    # Test 2: SQLAlchemy connection (only if direct connection worked)
    if direct_conn_result:
        results.append(("SQLAlchemy", test_sqlalchemy_connection()))
        
        # Test 3: Database tables
        results.append(("Database Tables", test_database_tables()))
    else:
        print("\n⚠ Skipping SQLAlchemy and table tests due to connection failure")
        results.append(("SQLAlchemy", False))
        results.append(("Database Tables", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✓ All tests passed! Database connection is working properly.")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        
        # Provide specific guidance for IP whitelist issues
        if current_ip:
            print("\n" + "=" * 60)
            print("IP WHITELIST TROUBLESHOOTING GUIDE")
            print("=" * 60)
            print(f"\n📋 DIAGNOSIS:")
            print(f"  Your current public IP: {current_ip}")
            print(f"  Whitelisted IP: {whitelisted_ip}")
            
            # Check if IPs match
            whitelist_ip_only = whitelisted_ip.split("/")[0] if "/" in whitelisted_ip else whitelisted_ip
            if whitelist_ip_only == current_ip:
                print(f"\n  ✓ IPs MATCH - but connection still failing?")
                print(f"\n  🔍 DETAILED TROUBLESHOOTING:")
                print(f"    1. 🔍 VERIFY SUPABASE SETTINGS:")
                print(f"       - Go to Supabase Dashboard → Settings → Database")
                print(f"       - Check 'Network Restrictions' section")
                print(f"       - Verify the IP is EXACTLY: {current_ip}/32")
                print(f"       - Make sure there are NO other restrictions")
                print(f"       - Ensure 'Restrict all access' is DISABLED")
                print(f"       - Try REMOVING the IP and RE-ADDING it")
                print(f"       - Click 'Save' and wait 2-3 minutes")
                print(f"\n    2. 🧪 TEST WITH 'ALLOW ALL ACCESS':")
                print(f"       - Temporarily enable 'Allow all access'")
                print(f"       - Run this test again - if it works, IP whitelist is the issue")
                print(f"       - If it still fails, the problem is elsewhere")
                print(f"\n    3. 🌐 IP MISMATCH POSSIBILITIES:")
                print(f"       - Supabase might see a different IP due to:")
                print(f"         • VPN/Proxy in use")
                print(f"         • Corporate firewall/NAT")
                print(f"         • ISP carrier-grade NAT")
                print(f"         • Multiple network interfaces")
                print(f"       - Check: Are you using a VPN? Corporate network?")
                print(f"\n    4. 🔧 SUPABASE DASHBOARD BUG:")
                print(f"       - Sometimes Supabase UI doesn't save correctly")
                print(f"       - Try: Remove IP → Save → Wait 1 min → Add IP → Save")
                print(f"       - Check Supabase connection logs if available")
                print(f"\n    5. 📝 CIDR NOTATION:")
                print(f"       - Make sure you're using: {current_ip}/32")
                print(f"       - /32 means single IP, /24 means IP range")
                print(f"       - Try with /24 if /32 doesn't work: {current_ip.rsplit('.', 1)[0]}.0/24")
                print(f"\n  💡 RECOMMENDED ACTIONS:")
                print(f"    1. Test with 'Allow all access' first (confirms connection works)")
                print(f"    2. Remove and re-add IP in Supabase dashboard")
                print(f"    3. Wait 3-5 minutes after saving")
                print(f"    4. Check Supabase logs for connection attempts")
                print(f"    5. Try adding IP range instead: {current_ip.rsplit('.', 1)[0]}.0/24")
            else:
                print(f"\n  ✗ IPs DO NOT MATCH")
                print(f"\n  💡 SOLUTION:")
                print(f"    Update Supabase whitelist to: {current_ip}/32")
                print(f"    Or use 'Allow all access' for development/testing")
            
            print(f"\n  📝 IP may change if you:")
            print(f"     - Switch networks (WiFi, mobile data, VPN)")
            print(f"     - Restart router (may get new IP from ISP)")
            print(f"     - Use different location")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

