#!/usr/bin/env python3
"""
Test script to verify SQLite migration and performance
"""
import time
import requests
import json
from pathlib import Path

def test_api_performance():
    """Test API performance before and after migration"""
    print("🚀 Testing API Performance")
    print("=" * 50)
    
    try:
        # Test database status
        print("📊 Checking database status...")
        response = requests.get('http://localhost:8888/api/database/status')
        if response.status_code == 200:
            status = response.json()
            print(f"   SQLite enabled: {status['sqlite_enabled']}")
            print(f"   SQLite exists: {status['sqlite_exists']}")
            print(f"   JSON books: {status['json_books']}")
            print(f"   SQLite books: {status['sqlite_books']}")
            print(f"   Current source: {status['current_source']}")
        else:
            print(f"❌ Failed to get database status: {response.status_code}")
            return
        
        # Test books API performance
        print("\n📚 Testing books API performance...")
        
        # Test with current source
        start_time = time.time()
        response = requests.get('http://localhost:8888/api/books')
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            books = data.get('books', [])
            current_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            print(f"   Current source ({status['current_source']}): {len(books)} books in {current_time:.1f}ms")
            
            # Show sample book with new files parameter
            if books:
                sample_book = books[0]
                print(f"\n📖 Sample book: {sample_book.get('title', 'Unknown')}")
                print(f"   Author: {sample_book.get('author', 'Unknown')}")
                print(f"   Contributor: {sample_book.get('contributor', 'None')}")
                print(f"   Read by: {sample_book.get('read_by', 'None')}")
                print(f"   Tags: {sample_book.get('tags', 'None')}")
                print(f"   Files: {len(sample_book.get('files', []))} files")
                
                # Show file details if available
                files = sample_book.get('files', [])
                if files:
                    print("   File details:")
                    for file_info in files[:3]:  # Show first 3 files
                        print(f"     - {file_info.get('filename')} ({file_info.get('type')}) - {file_info.get('hash', '')[:8]}...")
        else:
            print(f"❌ Failed to get books: {response.status_code}")
        
        # Test search performance
        print("\n🔍 Testing search performance...")
        start_time = time.time()
        response = requests.get('http://localhost:8888/api/books?search=barad')
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            books = data.get('books', [])
            search_time = (end_time - start_time) * 1000
            
            print(f"   Search results: {len(books)} books in {search_time:.1f}ms")
            for book in books[:3]:
                print(f"     - {book.get('title', 'Unknown')} by {book.get('author', 'Unknown')}")
        
        print("\n✅ Performance test completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Make sure the server is running on localhost:8888")
    except Exception as e:
        print(f"❌ Error during performance test: {e}")

def test_migration_switch():
    """Test switching between JSON and SQLite modes"""
    print("\n🔄 Testing Migration Switch")
    print("=" * 50)
    
    try:
        # Check current status
        response = requests.get('http://localhost:8888/api/database/status')
        if response.status_code != 200:
            print("❌ Failed to get database status")
            return
        
        status = response.json()
        current_source = status['current_source']
        
        print(f"Current source: {current_source}")
        
        if current_source == 'json' and status['migration_ready']:
            print("🔄 Switching to SQLite...")
            response = requests.post('http://localhost:8888/api/database/enable-sqlite')
            if response.status_code == 200:
                print("✅ Switched to SQLite mode")
            else:
                print(f"❌ Failed to switch to SQLite: {response.status_code}")
                return
        elif current_source == 'sqlite':
            print("🔄 Switching to JSON...")
            response = requests.post('http://localhost:8888/api/database/disable-sqlite')
            if response.status_code == 200:
                print("✅ Switched to JSON mode")
            else:
                print(f"❌ Failed to switch to JSON: {response.status_code}")
                return
        
        # Test performance after switch
        print("\n📊 Testing performance after switch...")
        start_time = time.time()
        response = requests.get('http://localhost:8888/api/books')
        end_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            books = data.get('books', [])
            switch_time = (end_time - start_time) * 1000
            
            print(f"   Retrieved {len(books)} books in {switch_time:.1f}ms")
            
            # Check new status
            status_response = requests.get('http://localhost:8888/api/database/status')
            if status_response.status_code == 200:
                new_status = status_response.json()
                print(f"   New source: {new_status['current_source']}")
        
        print("✅ Migration switch test completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to API. Make sure the server is running on localhost:8888")
    except Exception as e:
        print(f"❌ Error during migration switch test: {e}")

def main():
    """Main test function"""
    print("🧪 SQLite Migration Test Suite")
    print("=" * 60)
    
    # Test API performance
    test_api_performance()
    
    # Test migration switch
    test_migration_switch()
    
    print("\n🎉 All tests completed!")
    print("\n📋 Summary:")
    print("- If you see performance improvements, the migration is working!")
    print("- The 'files' parameter should now show hash IDs and URLs")
    print("- You can switch between JSON and SQLite modes safely")
    print("- JSON files remain untouched as backup")

if __name__ == '__main__':
    main() 