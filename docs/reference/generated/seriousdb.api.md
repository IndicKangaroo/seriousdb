# seriousdb.api

Synchronous Python API of seriousdb.

This module is the storage layer of seriousdb: other Python projects can import the package and call the functions exported here directly.

All functions are thread-safe.

### Functions

### count()

Return the number of key-value pairs in the database.

The database file is loaded automatically on first use.

* **Returns:**
  *int* – The number of stored key-value pairs.
* **Raises:**
  **OSError** – If the database file cannot be loaded.
* **Return type:**
  int

### delete(key)

Remove key and return the value it had.

The change is flushed to the database file before the function returns.

* **Parameters:**
  **key** (*str*) – Key to remove.
* **Returns:**
  *str* – The value key had before it was removed.
* **Raises:**
  * [**ResourceNotFoundError**](seriousdb.exceptions.md#seriousdb.exceptions.ResourceNotFoundError) – If key does not exist.
  * [**ServiceUnavailableError**](seriousdb.exceptions.md#seriousdb.exceptions.ServiceUnavailableError) – If no database has been loaded.
* **Return type:**
  str

### exists(key)

Return whether key exists in the database.

The database file is loaded automatically on first use.

* **Parameters:**
  **key** (*str*) – Key to look up.
* **Returns:**
  *bool* – `True` if key exists, `False` otherwise.
* **Return type:**
  bool

### get(key)

Return the value stored under key.

The database file is loaded automatically on first use.

* **Parameters:**
  **key** (*str*) – Key to look up.
* **Returns:**
  *str* – The value stored under key.
* **Raises:**
  * [**ResourceNotFoundError**](seriousdb.exceptions.md#seriousdb.exceptions.ResourceNotFoundError) – If key does not exist.
  * **OSError** – If the database file cannot be loaded.
* **Return type:**
  str

### get_all()

Return a snapshot of every key-value pair in the database.

The database file is loaded automatically on first use.

* **Returns:**
  *dict of str to str* – All stored key-value pairs.
* **Raises:**
  **OSError** – If the database file cannot be loaded.
* **Return type:**
  dict[str, str]

### get_bulk(keys)

Return the values stored under multiple keys.

Keys that do not exist are omitted from the result. The database file is loaded automatically on first use.

* **Parameters:**
  **keys** (*Iterable* *of* *str*) – Keys to look up.
* **Returns:**
  *dict of str to str* – A key-value pair for each requested key that exists in the database.
* **Raises:**
  **OSError** – If the database file cannot be loaded.
* **Return type:**
  dict[str, str]

### is_loaded()

Return whether a database has been loaded.

* **Returns:**
  *bool* – `True` if a database file has been loaded, `False` otherwise.
* **Return type:**
  bool

### load(filename='.sdb')

Load the database from filename, replacing the current data.

If the file does not exist, it is created with an empty database. If it is not valid UTF-8 JSON or does not contain a JSON object, it is renamed to `<filename>.corrupt-<unix timestamp>` (with a numeric suffix if that path already exists) and replaced with an empty database.

* **Parameters:**
  **filename** (*str* *or* *Path* *,* *optional*) – Path of the database file. Default to `DB_FILE`.
* **Raises:**
  **OSError** – If the file cannot be read, renamed or written.

### set(key, value)

Store value under key, overwriting any existing value.

The change is flushed to the database file before the function returns.

* **Parameters:**
  * **key** (*str*) – Key to store the value under.
  * **value** (*str*) – Value to store.
* **Returns:**
  *str* – The stored value.
* **Raises:**
  **OSError** – If the database file cannot be loaded or written.
* **Return type:**
  str
