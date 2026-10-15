import sqlite3
from pathlib import Path

db_path = Path(__file__).with_name("library.db")
connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("DROP TABLE IF EXISTS books")

cursor.execute("""
CREATE TABLE books (
    book_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,
    available_copies INTEGER NOT NULL CHECK (available_copies >= 0),
    times_borrowed INTEGER NOT NULL CHECK (times_borrowed >= 0)
)
""")

synthetic_books = [
    # Science
    ("A Brief History of Time", "Stephen Hawking", "Science", 5, 120),
    ("Cosmos", "Carl Sagan", "Science", 3, 95),
    ("The Selfish Gene", "Richard Dawkins", "Science", 0, 80),
    ("Brief Answers to the Big Questions", "Stephen Hawking", "Science", 4, 45),
    ("Sapiens", "Yuval Noah Harari", "Science", 6, 110),
    ("The Elegant Universe", "Brian Greene", "Science", 2, 35),
    ("Astrophysics for People in a Hurry", "Neil deGrasse Tyson", "Science", 0, 75),
    ("The Gene: An Intimate History", "Siddhartha Mukherjee", "Science", 3, 28),
    
    # Fiction
    ("To Kill a Mockingbird", "Harper Lee", "Fiction", 4, 150),
    ("1984", "George Orwell", "Fiction", 0, 140),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Fiction", 5, 85),
    ("The Hobbit", "J.R.R. Tolkien", "Fiction", 3, 130),
    ("Pride and Prejudice", "Jane Austen", "Fiction", 2, 90),
    ("Brave New World", "Aldous Huxley", "Fiction", 4, 65),
    ("The Catcher in the Rye", "J.D. Salinger", "Fiction", 1, 70),
    ("Fahrenheit 451", "Ray Bradbury", "Fiction", 0, 55),
    
    # History
    ("The Silk Roads", "Peter Frankopan", "History", 3, 40),
    ("Guns, Germs, and Steel", "Jared Diamond", "History", 2, 65),
    ("A People's History of the United States", "Howard Zinn", "History", 5, 30),
    ("The History of the Ancient World", "Susan Wise Bauer", "History", 2, 15),
    ("SPQR: A History of Ancient Rome", "Mary Beard", "History", 4, 22),
    ("The Wright Brothers", "David McCullough", "History", 3, 48),
    ("Churchill: A Walking with Destiny", "Andrew Roberts", "History", 1, 35),
    
    # Biography
    ("Steve Jobs", "Walter Isaacson", "Biography", 4, 105),
    ("Elon Musk", "Walter Isaacson", "Biography", 3, 90),
    ("Becoming", "Michelle Obama", "Biography", 6, 85),
    ("Long Walk to Freedom", "Nelson Mandela", "Biography", 2, 50),
    ("The Diary of a Young Girl", "Anne Frank", "Biography", 0, 115),
    ("Einstein: His Life and Universe", "Walter Isaacson", "Biography", 3, 60),
    ("Leonardo da Vinci", "Walter Isaacson", "Biography", 2, 42)
]

cursor.executemany(
    "INSERT INTO books (title, author, category, available_copies, times_borrowed) VALUES (?, ?, ?, ?, ?)",
    synthetic_books,
)
connection.commit()

count = cursor.execute("SELECT COUNT(*) FROM books").fetchone()[0]
print(f"Database ready: {db_path}")
print(f"Total book records: {count}")
connection.close()
