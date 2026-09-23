# seriousdb.exceptions

Application-specific exceptions.

### Exceptions

### *exception* ApplicationError(detail=None)

Bases: `Exception`

Base class for expected application errors.

Subclasses declare the HTTP status code and the machine readable error
code that the API layer uses when building a response.

* **Parameters:**
  **detail** (*str* *,* *optional*) – Human readable description of the error. Defaults to
  default_detail.
* **Variables:**
  * **status_code** (*int*) – HTTP status code of the error response.
  * **error_code** (*str*) – Machine readable error code of the error response.
  * **default_detail** (*str*) – Detail used when none is given.
  * **detail** (*str*) – Human readable description of this error.

### *exception* ResourceNotFoundError(detail=None)

Bases: [`ApplicationError`](#seriousdb.exceptions.ApplicationError)

A requested resource does not exist.

### *exception* ServiceUnavailableError(detail=None)

Bases: [`ApplicationError`](#seriousdb.exceptions.ApplicationError)

A dependency the application needs is currently not usable.
