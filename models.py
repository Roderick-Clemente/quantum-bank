import sqlite3
from datetime import datetime
import os

DATABASE = 'quantum_bank.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with tables and sample data"""
    conn = get_db()
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_type TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            balance REAL NOT NULL DEFAULT 0.0,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            recipient TEXT,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')

    # Create cards table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            card_type TEXT NOT NULL,
            card_number TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            cvv TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')

    conn.commit()

    # Check if we need to add sample data
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        create_sample_data(conn)

    conn.close()

def create_sample_data(conn):
    """Create sample users and accounts for demo purposes"""
    cursor = conn.cursor()

    # Create demo user
    cursor.execute('''
        INSERT INTO users (username, email, full_name)
        VALUES (?, ?, ?)
    ''', ('demo', 'demo@quantumbank.com', 'Demo User'))

    user_id = cursor.lastrowid

    # Create checking account
    cursor.execute('''
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
    ''', (user_id, 'checking', 'QB-CHK-100001', 5420.50))

    checking_id = cursor.lastrowid

    # Create savings account
    cursor.execute('''
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
    ''', (user_id, 'savings', 'QB-SAV-200001', 12850.75))

    savings_id = cursor.lastrowid

    # Create credit account
    cursor.execute('''
        INSERT INTO accounts (user_id, account_type, account_number, balance)
        VALUES (?, ?, ?, ?)
    ''', (user_id, 'credit', 'QB-CC-300001', -1234.20))

    credit_id = cursor.lastrowid

    # Add sample transactions for checking account
    transactions = [
        (checking_id, 'deposit', 1500.00, 'Payroll Deposit', 'Acme Corp', 'completed'),
        (checking_id, 'withdrawal', -45.20, 'Coffee Shop', 'Blue Bottle Coffee', 'completed'),
        (checking_id, 'withdrawal', -125.00, 'Grocery Shopping', 'Whole Foods', 'completed'),
        (checking_id, 'withdrawal', -89.99, 'Online Purchase', 'Amazon', 'completed'),
        (checking_id, 'transfer', -500.00, 'Transfer to Savings', 'Savings Account', 'completed'),
    ]

    for trans in transactions:
        cursor.execute('''
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', trans)

    # Add sample transactions for savings account
    savings_transactions = [
        (savings_id, 'deposit', 5000.00, 'Initial Deposit', 'Self', 'completed'),
        (savings_id, 'transfer', 500.00, 'Transfer from Checking', 'Checking Account', 'completed'),
        (savings_id, 'interest', 25.75, 'Monthly Interest', 'Quantum Bank', 'completed'),
    ]

    for trans in savings_transactions:
        cursor.execute('''
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', trans)

    # Add sample transactions for credit account
    credit_transactions = [
        (credit_id, 'charge', -234.50, 'Restaurant', 'Chez Pierre', 'completed'),
        (credit_id, 'charge', -89.99, 'Gas Station', 'Shell', 'completed'),
        (credit_id, 'charge', -599.99, 'Electronics', 'Best Buy', 'completed'),
        (credit_id, 'payment', 500.00, 'Credit Card Payment', 'Online Payment', 'completed'),
    ]

    for trans in credit_transactions:
        cursor.execute('''
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', trans)

    # Add sample cards
    cards = [
        (checking_id, 'debit', '**** **** **** 1234', '12/2026', '123'),
        (credit_id, 'credit', '**** **** **** 5678', '09/2027', '456'),
    ]

    for card in cards:
        cursor.execute('''
            INSERT INTO cards (account_id, card_type, card_number, expiry_date, cvv)
            VALUES (?, ?, ?, ?, ?)
        ''', card)

    conn.commit()

# Database query functions
def get_user_by_username(username):
    """Get user by username"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_accounts_by_user(user_id):
    """Get all accounts for a user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at', (user_id,))
    accounts = cursor.fetchall()
    conn.close()
    return [dict(account) for account in accounts]

def get_account_by_id(account_id):
    """Get account by ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
    account = cursor.fetchone()
    conn.close()
    return dict(account) if account else None

def get_transactions_by_account(account_id, limit=10):
    """Get transactions for an account"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM transactions
        WHERE account_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (account_id, limit))
    transactions = cursor.fetchall()
    conn.close()
    return [dict(trans) for trans in transactions]

def get_all_transactions_by_user(user_id, limit=20):
    """Get all transactions for a user across all accounts"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, a.account_type, a.account_number
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.user_id = ?
        ORDER BY t.created_at DESC
        LIMIT ?
    ''', (user_id, limit))
    transactions = cursor.fetchall()
    conn.close()
    return [dict(trans) for trans in transactions]

def get_cards_by_account(account_id):
    """Get cards for an account"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cards WHERE account_id = ?', (account_id,))
    cards = cursor.fetchall()
    conn.close()
    return [dict(card) for card in cards]

def create_transaction(account_id, transaction_type, amount, description, recipient=''):
    """Create a new transaction"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
        VALUES (?, ?, ?, ?, ?)
    ''', (account_id, transaction_type, amount, description, recipient))

    # Update account balance
    cursor.execute('''
        UPDATE accounts
        SET balance = balance + ?
        WHERE id = ?
    ''', (amount, account_id))

    transaction_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return transaction_id

def transfer_money(from_account_id, to_account_id, amount, description='Transfer'):
    """Transfer money between accounts"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Check if source account has sufficient funds
        cursor.execute('SELECT balance, account_number FROM accounts WHERE id = ?', (from_account_id,))
        from_account = cursor.fetchone()

        cursor.execute('SELECT account_number FROM accounts WHERE id = ?', (to_account_id,))
        to_account = cursor.fetchone()

        if not from_account or not to_account:
            conn.close()
            return False, "Account not found"

        if from_account['balance'] < amount:
            conn.close()
            return False, "Insufficient funds"

        # Deduct from source account
        cursor.execute('''
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
            VALUES (?, ?, ?, ?, ?)
        ''', (from_account_id, 'transfer', -amount, description, to_account['account_number']))

        cursor.execute('''
            UPDATE accounts SET balance = balance - ? WHERE id = ?
        ''', (amount, from_account_id))

        # Add to destination account
        cursor.execute('''
            INSERT INTO transactions (account_id, transaction_type, amount, description, recipient)
            VALUES (?, ?, ?, ?, ?)
        ''', (to_account_id, 'transfer', amount, description, from_account['account_number']))

        cursor.execute('''
            UPDATE accounts SET balance = balance + ? WHERE id = ?
        ''', (amount, to_account_id))

        conn.commit()
        conn.close()
        return True, "Transfer successful"

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)
