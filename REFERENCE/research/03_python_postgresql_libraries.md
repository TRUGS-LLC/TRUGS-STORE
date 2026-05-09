# **Architectural Evaluation of Python PostgreSQL Drivers for High-Performance Graph Storage**

The construction of a graph storage layer on top of a relational database like PostgreSQL requires a fundamental understanding of how the application interacts with the database engine. In high-performance scenarios—where sub-millisecond point lookups and complex recursive traversals under ten milliseconds are non-negotiable—the choice of driver dictates the absolute ceiling of the system’s capabilities. This report provides a technical analysis of the three primary libraries in the Python ecosystem: psycopg3, asyncpg, and SQLAlchemy, specifically through the lens of graph-oriented data structures, asynchronous concurrency, and production-grade robustness.

## **Driver Internals and Protocol Architectures**

The performance differential between database drivers is primarily rooted in their implementation of the PostgreSQL wire protocol. For a graph storage layer, where every node traversal may involve a network round-trip or a complex multi-step recursive query, the efficiency of this communication layer is paramount.

### **The binary protocol and implementation paradigms**

The PostgreSQL wire protocol supports two primary modes of data transmission: text and binary. Traditional drivers often relied on the text protocol for broad compatibility, but modern high-performance drivers have moved toward binary representations to reduce serialization overhead.

The asyncpg library is distinctive because it implements the PostgreSQL binary protocol natively in C using a thin Python wrapper.1 By bypassing the standard libpq library—the C client library traditionally used by almost all other drivers—asyncpg achieves exceptional speed.1 This native implementation allows asyncpg to ignore the Python DB-API 2.0 specification, which its authors deemed too synchronous and restrictive for an optimized asynchronous driver.3 The result is a driver that can communicate with the server with minimal translation overhead, particularly for complex types like JSONB, ARRAY, and composite types often used in graph modeling.1

In contrast, psycopg3 (officially rebranded as simply psycopg) uses libpq for low-level communication but is written primarily in Python.1 This design choice prioritizes flexibility and extensibility. Unlike its predecessor psycopg2, which was primarily synchronous with async features "bolted on," psycopg3 was designed from the ground up to provide a unified API for both synchronous and asynchronous operations.1 While psycopg3 can utilize the binary protocol, it defaults to a hybrid approach that favors server-side binding, which enhances security and can improve execution plans by allowing the database to handle parameter types natively.6

SQLAlchemy occupies a higher level of abstraction. It does not implement the wire protocol itself but acts as a management layer over drivers like asyncpg or psycopg3.1 For graph storage, SQLAlchemy provides two distinct interfaces: "Core," which is an expression-based SQL builder, and "ORM," which maps database rows to Python objects. The choice of underlying driver—referred to as the "dialect" in SQLAlchemy—determines the baseline performance, while SQLAlchemy adds its own layer of overhead for statement compilation and result set marshalling.9

### **Impact of C-Extensions and Native Async Support**

The performance of an asynchronous driver is heavily influenced by how it interacts with the Python asyncio event loop. asyncpg is "async-native," meaning its internal state machines are designed specifically for the asynchronous paradigm.1 This allows it to handle thousands of concurrent requests with minimal CPU overhead per request. Its implementation in C means that most of the heavy lifting of packet parsing and buffer management happens outside the Python Global Interpreter Lock (GIL), though it is important to note that the library is still bound by the CPython C-API, which limits its compatibility with alternative implementations like PyPy.3

psycopg3 offers separate Connection and AsyncConnection classes.1 Its asynchronous implementation is robust but, because it is written in Python and wraps the synchronous libpq, it can sometimes exhibit slightly higher latency in raw throughput benchmarks compared to the pure C implementation of asyncpg.1 However, for many real-world applications, this difference is negligible, as network latency and database execution time usually dominate the total response time.1

## **Comprehensive Performance Analysis**

To evaluate these libraries for a graph storage layer, performance must be analyzed across three categories: simple point queries (node lookups), complex traversals (recursive CTEs), and high-volume mutations (batch inserts).

### **Latency Profiles for Node Lookups**

For a graph storage layer, sub-millisecond query execution is a critical requirement for simple operations like retrieving a node by its primary key. Benchmarks consistently show that asyncpg is the fastest driver for these "PointGet" operations.2

| Database/Driver Combination | P50 Latency (ms) | P95 Latency (ms) | Throughput (ops/sec) |
| :---- | :---- | :---- | :---- |
| HelixDB (Reference) | 1.07 | 1.29 | 90,238.4 |
| PostgreSQL \+ asyncpg (optimized) | 6.46 | 6.61 | 15,435.0 |
| PostgreSQL \+ psycopg3 (async) | 88.11 | 216.74 | 2,698.62 |
| PostgreSQL \+ psycopg3 (sync) | 304.00 | 450.00 | 779.80 |

The table above, synthesized from multiple benchmarking sources, highlights the significant performance gap between asynchronous and synchronous drivers.12 At a concurrency level of 100, asyncpg can process over 15,000 operations per second with single-digit millisecond latency.12 While psycopg3 async is significantly faster than its synchronous counterpart, it often shows higher tail latency (P95) in high-concurrency environments compared to asyncpg.13

### **Complex Graph Traversals and Recursive CTEs**

Graph traversals involve following edges through multiple hops. In PostgreSQL, this is typically implemented using Recursive Common Table Expressions (CTEs). As query complexity increases, the time spent in the database's execution engine begins to outweigh the driver's overhead.

In a "OneHop" traversal test—fetching all items a user has interacted with, involving approximately 400 edges—PostgreSQL's performance is governed by join efficiency and index scanning.12 At 100 concurrent users, the average latency for this traversal in PostgreSQL is approximately 87.84ms, significantly exceeding the target \<10ms requirement for complex traversals.12 This indicates that for a graph storage layer to meet high-performance targets on PostgreSQL, the architecture must rely heavily on optimized indexes (such as covering indexes) and possibly denormalization or caching, rather than raw driver speed alone.12

However, the choice of driver still matters for result marshalling. When a traversal returns a large subgraph (e.g., 5,000 rows), the overhead of converting database types to Python objects becomes a bottleneck. In tests reading 5,000 rows, psycopg3 async actually showed a slight advantage over asyncpg in some scenarios, handling 110.44 requests per second compared to asyncpg's 94.74 requests per second.13 This suggests that while asyncpg is superior for high-frequency small queries, psycopg3 may be more efficient at handling larger result sets due to its redesigned connection and cursor management.13

### **High-Volume Ingestion and Batch Mutations**

Graph mutations, such as ingesting millions of edges from a CSV or API, require drivers that can push the limits of PostgreSQL's ingestion throughput.

| Ingestion Method | Abstraction Level | Optimal Throughput | Best Use Case |
| :---- | :---- | :---- | :---- |
| COPY Protocol | Driver-level (psycopg3/asyncpg) | Up to 2M records/sec | Bulk initial loads, ETL |
| executemany | Driver-level | High | Batch updates (100-1000 nodes) |
| Core execute | SQLAlchemy Core | Moderate | Structured ingestion with safety |
| ORM add\_all | SQLAlchemy ORM | Low | Small batches where logic \> speed |

The COPY protocol is the fastest method for data ingestion in PostgreSQL.8 Both psycopg3 and asyncpg provide native support for COPY, allowing the application to stream data directly into a table.15 psycopg3's support for COPY is particularly well-regarded for its ease of use with Python objects.15 In contrast, using SQLAlchemy ORM for bulk operations introduces massive overhead due to its internal state tracking and unit-of-work pattern, making it unsuitable for the high-volume mutations required in a graph storage layer.8

## **Feature Support for Graph Workloads**

Beyond raw speed, the storage layer requires specific PostgreSQL features to represent and query graph data effectively.

### **Recursive CTE Implementation and API**

Recursive CTEs are the standard SQL mechanism for graph traversal. They consist of an anchor member (the starting node) and a recursive member (the step to the next neighbor), joined by a UNION or UNION ALL.17

SQL

\-- Recursive CTE for finding all connected components of node 'A'  
WITH RECURSIVE cc AS (  
    SELECT u, v FROM edges WHERE u \= 'A' OR v \= 'A'  
    UNION  
    SELECT e.u, e.v FROM edges e  
    INNER JOIN cc ON e.u \= cc.v OR e.v \= cc.u  
)  
SELECT \* FROM cc;

asyncpg and psycopg3 require the developer to write this SQL manually.1 While this offers maximum control, it provides no type safety or protection against syntax errors. SQLAlchemy Core, however, provides a programmatic builder for recursive CTEs.20 Using the .cte(recursive=True) method, developers can build these complex queries using Python expressions, which SQLAlchemy then compiles into the correct SQL syntax for the PostgreSQL version being used.20

### **JSONB and Schema-less Flexibility**

In a property graph, nodes and edges often have a variable set of attributes. PostgreSQL's JSONB type is ideal for this, as it stores JSON data in a decomposed binary format that supports efficient indexing and querying.14

* **JSONB in SQLAlchemy**: Provides the most robust support. It includes a dedicated JSONB type and a Comparator class that maps PostgreSQL-specific operators like @\> (contains) and ? (has\_key) to Python methods.14  
* **JSONB in asyncpg**: By default, asyncpg returns JSONB columns as strings. However, it allows for the registration of custom codecs, which can automate the conversion between JSONB and Python dictionaries using high-speed libraries like orjson.24  
* **JSONB in psycopg3**: Offers a highly customizable type adaptation system that handles the conversion between Python types and JSONB seamlessly.1

The performance of JSONB is closely tied to indexing. To meet the sub-millisecond query requirement, the storage layer must utilize GIN (Generalized Inverted Index) indexes on JSONB columns.14 SQLAlchemy makes this straightforward by allowing the index type to be specified in the table definition using the postgresql\_using='gin' parameter.14

### **ARRAY Types and Path Tracking**

A common requirement in graph traversal is not just finding a destination node, but also the path taken to get there. PostgreSQL's ARRAY type is frequently used in recursive CTEs to build a path of visited node IDs, which also serves as a mechanism to detect and prevent cycles in the graph.18

Both asyncpg and psycopg3 have excellent support for PostgreSQL arrays, mapping them directly to Python lists.2 asyncpg is particularly efficient at handling arrays of complex types, though it may require manual codec registration when used with some specialized extensions.16

## **Connection Pooling and Production Scaling**

For a library supporting 100+ concurrent connections, the strategy for connection pooling is as important as the driver itself.

### **Internal vs. External Pooling**

Establishing a new connection to PostgreSQL is expensive, requiring the forking of a backend process on the server. A connection pool maintains a set of open connections and hands them out to the application as needed.

* **asyncpg**: Features a built-in, highly optimized connection pool.1 It is designed for asyncio and manages the lifecycle of connections without external dependencies.1  
* **psycopg3**: Uses the psycopg\_pool library, which provides both ConnectionPool and AsyncConnectionPool.1 It is a mature, standalone library that offers a consistent experience for both sync and async workloads.  
* **SQLAlchemy**: Implements its own pooling logic that sits above the driver. It provides sophisticated features like connection recycling, overflow management, and "pessimistic" connection testing.14

In many high-scale production environments, an external pooler like **pgBouncer** is used to manage thousands of connections across multiple application instances. However, using pgBouncer in "transaction" or "statement" pooling mode can break certain driver optimizations, specifically prepared statements.

### **The Prepared Statement Dilemma**

Prepared statements allow the database to parse and plan a query once and reuse that plan multiple times, which is essential for minimizing latency in repetitive graph lookups.1

asyncpg makes heavy use of prepared statements automatically.24 However, if pgBouncer routes subsequent executions of a "prepared" query to a different backend PostgreSQL process that does not have that query prepared, the query will fail with an error.4 By 2025, pgBouncer has improved support for protocol-level prepared plans, but it requires explicit configuration.29

| Pooling Mode | Prepared Statement Support | Best Practice |
| :---- | :---- | :---- |
| Session | Full | Recommended for asyncpg/psycopg3 if connection counts are manageable. |
| Transaction | Partial | Set statement\_cache\_size=0 in asyncpg or use NullConnectionPool in psycopg3. |
| Statement | None | Avoid for anything other than simple autocommit queries. |

psycopg3 handles this more flexibly than asyncpg by allowing for "server-side" vs "client-side" binding and offering the NullConnectionPool specifically for environments where an external pooler like pgBouncer is already handling the connection lifecycle.6

## **API Ergonomics and Developer Experience**

The goal of the storage library is to provide a "clean API" for the consumer. This requires balancing performance with developer productivity.

### **Abstraction Design: Driver vs. Core**

* **Manual SQL (asyncpg/psycopg3)**: The developer writes raw SQL strings. This provides the best performance but is error-prone and harder to maintain.5 It makes the abstraction layer responsible for all SQL generation, which can become complex for dynamic graph queries.  
* **Query Builder (SQLAlchemy Core)**: Offers a Pythonic way to build queries. It provides a "middle ground" between raw SQL and an ORM, offering safety and abstraction without the full performance penalty of the ORM.8  
* **The Hybrid Approach**: Many high-performance libraries use SQLAlchemy Core for query generation but execute the generated SQL using a raw asynchronous driver for maximum speed.5

### **Type Safety and Integration with Pydantic**

Modern Python backend development relies heavily on Pydantic for data validation and type safety. psycopg3 is designed with modern Python in mind, offering excellent support for static typing and "Row Factories".5 A Row Factory allows the driver to automatically return rows as Pydantic models, which is a significant "killer feature" for developer ergonomics in graph libraries that need to return complex Node and Edge objects.5

While asyncpg can be made to work with Pydantic, it is often more verbose and requires manual mapping of results.5 SQLAlchemy's 2.0 release also significantly improved its type hint support, making it a viable choice for type-safe applications.9

## **Transactional Integrity in Graph Mutations**

Graph mutations are rarely isolated to a single row. Creating a relationship typically involves verifying the existence of two nodes and inserting an edge between them.

### **ACID Guarantees and Deadlock Mitigation**

In high-concurrency environments, graph mutations are prone to deadlocks—for example, when two transactions try to update different parts of the same relationship in opposite orders.

1. **Isolation Levels**: For graph integrity, READ COMMITTED is often insufficient. REPEATABLE READ or SERIALIZABLE isolation may be required to prevent "lost updates".14  
2. **Explicit Locking**: In some cases, using SELECT FOR UPDATE on nodes before creating edges between them is necessary to ensure consistency, though this can significantly impact throughput.  
3. **Conflict Handling**: INSERT... ON CONFLICT (Upsert) is a critical PostgreSQL feature for graph ingestion, allowing nodes to be created or updated in a single atomic operation.14 All three libraries support this syntax, though SQLAlchemy Core provides the most structured way to specify the DO UPDATE or DO NOTHING clauses.14

## **Production Adoption and Ecosystem Maturity**

The choice of library is also a choice of the community and ecosystem that supports it.

### **Market Share and Framework Integration**

* **SQLAlchemy**: The undisputed industry leader. It is the default choice for most Django and Flask applications and has a massive ecosystem of extensions (like Alembic for migrations).8 Its async support in 2.0 is now mature and production-ready.  
* **asyncpg**: The "gold standard" for performance-critical async Python applications. It is the driver of choice for the FastAPI community and is used by companies requiring the absolute lowest latency.5  
* **psycopg3**: Rapidly becoming the new standard. It combines the legacy and trust of psycopg2 with modern async capabilities.5

### **Maintenance and Stability**

psycopg3 has been in development since 2020 and saw its first stable release in 2021\.5 It is actively maintained by the same team that kept psycopg2 as the leading driver for over a decade. asyncpg is maintained by the MagicStack team and has been stable since its 1.0 release, with no major breaking changes in recent years.2 SQLAlchemy 2.0, released in 2023, was a major modernization of the library that unified the "Core" and "ORM" styles and made async a first-class citizen.9

## **The Async Architecture Fit**

When building a library for the modern Python ecosystem, the "all or nothing" nature of async/await is a critical factor.

### **Why Async?**

The primary advantage of async for database drivers is not that individual queries are faster—in fact, they are often slightly slower due to the overhead of the event loop—but that the application can handle many more concurrent requests.11 In a graph storage layer serving a web API, an async driver allows the server to remain responsive while waiting for the database to complete a complex 50ms traversal, rather than blocking an entire thread.31

### **Overhead of Abstraction Layers**

The "cost" of using SQLAlchemy async vs. asyncpg directly is approximately 0.1ms to 0.3ms per query in overhead.10 For a sub-millisecond point lookup, this is a 20-30% penalty. For a 10ms traversal, it is a 2-3% penalty.

| Operation Type | Raw asyncpg Latency | SQLAlchemy Async Overhead | Relative Impact |
| :---- | :---- | :---- | :---- |
| Simple SELECT | \~0.2ms | \+0.3ms | **High** |
| Complex Join | \~2.0ms | \+0.3ms | **Moderate** |
| Recursive CTE | \~15.0ms | \+0.3ms | **Low** |

This data suggests that if the library is primarily intended for complex graph analysis, the ergonomics of SQLAlchemy may be worth the marginal performance cost. If the library is intended for high-frequency low-latency lookups (e.g., a social media feed or a real-time recommendation engine), the raw speed of asyncpg or psycopg3 is likely required.1

## **Strategic Recommendations**

Selecting the best library for a high-performance graph storage layer involves a tiered decision based on the specific performance vs. ergonomics requirements of the project.

### **Recommendation 1: Start with psycopg3 for a General-Purpose Library**

psycopg3 is the optimal choice for a library that needs to balance extreme performance with modern developer experience. Its "Row Factories" and native static typing make it the easiest driver to build a clean, Pydantic-friendly abstraction upon, while its performance is more than sufficient for almost all production use cases.1 Its unified sync/async API also allows the library to support the widest possible range of client applications.

### **Recommendation 2: Use asyncpg for Niche, Extreme Throughput Systems**

If the project is a specialized service where the only goal is maximum raw throughput and the developers are comfortable with the steeper learning curve of a low-level API, asyncpg remains the performance king.1 It is particularly suited for internal microservices that do not need to expose a generic, user-friendly API but must handle tens of thousands of requests per second on a single node.

### **Recommendation 3: Use SQLAlchemy Core for Query Construction**

Regardless of the driver choice, SQLAlchemy Core is the recommended tool for *generating* the SQL for recursive CTEs and complex graph filters. It provides a level of safety and database-version portability that is impossible to achieve with raw string formatting.9 The library can use SQLAlchemy Core to build the queries and then execute them using the underlying driver for the best of both worlds.

## **Synthesis of Findings and Trade-offs**

The decision between these libraries is not merely technical but strategic. The following matrix summarizes the fundamental trade-offs identified in the research.

| Attribute | psycopg3 | asyncpg | SQLAlchemy (Core) |
| :---- | :---- | :---- | :---- |
| **Raw Speed** | High | **Highest** | Moderate |
| **Async Support** | Unified Sync/Async | **Native Async** | Async via Driver |
| **Developer Ergonomics** | **Best (Modern Python)** | Moderate (Low-level) | Excellent (Pythonic) |
| **Graph Features** | Manual SQL | Manual SQL | **Query Builder for CTEs** |
| **Ingestion** | **Best (COPY \+ Objects)** | High (COPY) | Moderate |
| **Maturity** | High (psycopg2 legacy) | High | **Industry Standard** |

### **Implementation Specifics for Graph Storage**

To achieve the performance goals of sub-millisecond queries and \<10ms complex traversals on PostgreSQL:

1. **Batching**: Implement node/edge creation using the COPY protocol supported by psycopg3 or asyncpg. This is orders of magnitude faster than individual INSERT statements.8  
2. **Indexing**: Enforce the use of GIN indexes on JSONB columns and B-tree indexes on foreign keys (source\_id, target\_id). Without these, PostgreSQL will fall back to sequential scans, making graph traversal impossible at scale.14  
3. **Recursion Depth**: When implementing recursive CTEs, always include a depth limit or a statement timeout to prevent runaway queries on highly connected subgraphs.26  
4. **Path Materialization**: Consider storing the path as an ARRAY within the recursive CTE to detect cycles and return the full traversal path to the user in a single query.18

## **Migration and Future-Proofing**

If a project chooses one of these libraries and later needs to switch, the "hardness" of that migration varies significantly:

* **Switching Driver (asyncpg \<-\> psycopg3)**: Relatively straightforward if the library has a clean abstraction layer and uses standard SQL. The main differences are in the parameter syntax ($1 vs %s) and the connection pool API.1  
* **Moving from SQLAlchemy to Raw Driver**: High difficulty. SQLAlchemy's expression language is tightly integrated into the code. Replacing it requires rewriting almost all query generation logic.5  
* **Moving from Raw Driver to SQLAlchemy**: Moderate difficulty. It requires wrapping existing SQL strings in text() constructs or rewriting them as SQLAlchemy expressions.9

In summary, for a high-performance graph storage abstraction, the optimal architecture uses **SQLAlchemy Core for query generation** and **psycopg3 (async) for execution**. This setup provides the required performance for sub-millisecond operations while ensuring the library is maintainable, type-safe, and production-ready for the next decade of Python development.

#### **Works cited**

1. Asynchronous Python Postgres Drivers A Deep Dive into Performance Features and Usability | Leapcell, accessed February 17, 2026, [https://leapcell.io/blog/asynchronous-python-postgres-drivers-a-deep-dive-into-performance-features-and-usability](https://leapcell.io/blog/asynchronous-python-postgres-drivers-a-deep-dive-into-performance-features-and-usability)  
2. asyncpg \- PyPI, accessed February 17, 2026, [https://pypi.org/project/asyncpg/](https://pypi.org/project/asyncpg/)  
3. Differences from Psycopg2 \- Hacker News, accessed February 17, 2026, [https://news.ycombinator.com/item?id=37834861](https://news.ycombinator.com/item?id=37834861)  
4. Frequently Asked Questions — asyncpg Documentation, accessed February 17, 2026, [https://magicstack.github.io/asyncpg/current/faq.html](https://magicstack.github.io/asyncpg/current/faq.html)  
5. FastAPI, Pydantic, Psycopg3: The Ultimate Trio for Python Web APIs, accessed February 17, 2026, [https://spwoodcock.dev/blog/2024-10-fastapi-pydantic-psycopg/](https://spwoodcock.dev/blog/2024-10-fastapi-pydantic-psycopg/)  
6. Possible performance improvements of psycopg3 support in Django 4.2 \- ORM, accessed February 17, 2026, [https://forum.djangoproject.com/t/possible-performance-improvements-of-psycopg3-support-in-django-4-2/18978](https://forum.djangoproject.com/t/possible-performance-improvements-of-psycopg3-support-in-django-4-2/18978)  
7. Passing parameters to SQL queries \- psycopg 3.3.3.dev1 ..., accessed February 17, 2026, [https://www.psycopg.org/psycopg3/docs/basic/params.html\#binary-parameters](https://www.psycopg.org/psycopg3/docs/basic/params.html#binary-parameters)  
8. Faster Is Not Always Better: Choosing the Right PostgreSQL Insert Strategy in Python (+Benchmarks) | Towards Data Science, accessed February 17, 2026, [https://towardsdatascience.com/faster-is-not-always-better-choosing-the-right-postgresql-insert-strategy-in-python-benchmarks/](https://towardsdatascience.com/faster-is-not-always-better-choosing-the-right-postgresql-insert-strategy-in-python-benchmarks/)  
9. Ultimate guide to SQLAlchemy library in python \- Deepnote, accessed February 17, 2026, [https://deepnote.com/blog/ultimate-guide-to-sqlalchemy-library-in-python](https://deepnote.com/blog/ultimate-guide-to-sqlalchemy-library-in-python)  
10. A simple performance comparison for SQLAlchemy \+ asyncpg \- GitHub, accessed February 17, 2026, [https://github.com/dmig/asyncpg-sqlalchemy-vs-raw](https://github.com/dmig/asyncpg-sqlalchemy-vs-raw)  
11. Exploring the Differences Between asyncpg and psycopg2: Which Python Library Should You Use? \- YouTube, accessed February 17, 2026, [https://www.youtube.com/watch?v=pTEFd1L33Yk](https://www.youtube.com/watch?v=pTEFd1L33Yk)  
12. Graph-Vector Database Performance Benchmarks (2025) \- HelixDB, accessed February 17, 2026, [https://docs.helix-db.com/benchmarks/v1](https://docs.helix-db.com/benchmarks/v1)  
13. Psycopg 3 vs Asyncpg \- fernandoarteaga.dev, accessed February 17, 2026, [https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/](https://fernandoarteaga.dev/blog/psycopg-vs-asyncpg/)  
14. PostgreSQL — SQLAlchemy 2.1 Documentation, accessed February 17, 2026, [http://docs.sqlalchemy.org/en/latest/dialects/postgresql.html](http://docs.sqlalchemy.org/en/latest/dialects/postgresql.html)  
15. psycopg \- Crunchy Data Customer Portal, accessed February 17, 2026, [https://access.crunchydata.com/documentation/psycopg3/3.1.9/pdf/psycopg3.pdf](https://access.crunchydata.com/documentation/psycopg3/3.1.9/pdf/psycopg3.pdf)  
16. Python PGWire Guide \- QuestDB, accessed February 17, 2026, [https://questdb.com/docs/query/pgwire/python/](https://questdb.com/docs/query/pgwire/python/)  
17. Graph Algorithms in a Database: Recursive CTEs and Topological Sort with Postgres, accessed February 17, 2026, [https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)  
18. Recursive SQL Queries with PostgreSQL | Martin Heinz | Personal Website & Blog, accessed February 17, 2026, [https://martinheinz.dev/blog/18](https://martinheinz.dev/blog/18)  
19. Implementing Graph queries in a Relational Database | by Ademar Victorino, accessed February 17, 2026, [https://blog.whiteprompt.com/implementing-graph-queries-in-a-relational-database-7842b8075ca8](https://blog.whiteprompt.com/implementing-graph-queries-in-a-relational-database-7842b8075ca8)  
20. Recursive CTEs results as ORM model instances in SQLModel or SQLAlchemy, accessed February 17, 2026, [https://rossmasters.com/recursive-ctes-results-as-orm-model-instances-in-sqlmodel-or-sqlalchemy/](https://rossmasters.com/recursive-ctes-results-as-orm-model-instances-in-sqlmodel-or-sqlalchemy/)  
21. How do I select a recursive entity in sqlalchemy \- Stack Overflow, accessed February 17, 2026, [https://stackoverflow.com/questions/79550627/how-do-i-select-a-recursive-entity-in-sqlalchemy](https://stackoverflow.com/questions/79550627/how-do-i-select-a-recursive-entity-in-sqlalchemy)  
22. SQLAlchemy basic recursive CTE example \- hierarchical tree query \- Stack Overflow, accessed February 17, 2026, [https://stackoverflow.com/questions/57459388/sqlalchemy-basic-recursive-cte-example-hierarchical-tree-query](https://stackoverflow.com/questions/57459388/sqlalchemy-basic-recursive-cte-example-hierarchical-tree-query)  
23. NCI-GDC/psqlgraph: Library for graph-like storage in postgresql using sqlalchemy \- GitHub, accessed February 17, 2026, [https://github.com/NCI-GDC/psqlgraph](https://github.com/NCI-GDC/psqlgraph)  
24. asyncpg Usage — asyncpg Documentation, accessed February 17, 2026, [https://magicstack.github.io/asyncpg/current/usage.html\#type-conversion](https://magicstack.github.io/asyncpg/current/usage.html#type-conversion)  
25. Performance Testing of PostgreSQL with JSON Data: 1 to 1000 Concurrency with Data up to 50 Million Rows | by Chalindu Kodikara | Medium, accessed February 17, 2026, [https://medium.com/@chalindu/comprehensive-performance-testing-of-postgresql-with-jsonb-data-1-to-1000-concurrency-with-data-up-636029d8e9d4](https://medium.com/@chalindu/comprehensive-performance-testing-of-postgresql-with-jsonb-data-1-to-1000-concurrency-with-data-up-636029d8e9d4)  
26. Graph Retrieval using Postgres Recursive CTEs, accessed February 17, 2026, [https://www.sheshbabu.com/posts/graph-retrieval-using-postgres-recursive-ctes/](https://www.sheshbabu.com/posts/graph-retrieval-using-postgres-recursive-ctes/)  
27. Unexpected Performance Bottleneck in Async SQLAlchemy Compared to Sync \#12353, accessed February 17, 2026, [https://github.com/sqlalchemy/sqlalchemy/discussions/12353](https://github.com/sqlalchemy/sqlalchemy/discussions/12353)  
28. Prepared statements unexpected behavior with psycopg and PgBouncer \#1151 \- GitHub, accessed February 17, 2026, [https://github.com/psycopg/psycopg/issues/1151](https://github.com/psycopg/psycopg/issues/1151)  
29. PgBouncer features, accessed February 17, 2026, [https://www.pgbouncer.org/features.html](https://www.pgbouncer.org/features.html)  
30. Asynchronous I/O (asyncio) — SQLAlchemy 2.1 Documentation, accessed February 17, 2026, [https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html\#using-isolation-levels-with-async-session](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-isolation-levels-with-async-session)  
31. Async SQLAlchemy Journey: From Confusion to Clarity \- Shane's Personal Blog, accessed February 17, 2026, [https://shanechang.com/p/async-sqlalchemy-journey/](https://shanechang.com/p/async-sqlalchemy-journey/)  
32. Async vs Sync in FastAPI \+ SQLAlchemy: Which Should You Use? \- Reddit, accessed February 17, 2026, [https://www.reddit.com/r/FastAPI/comments/1p0s8sm/async\_vs\_sync\_in\_fastapi\_sqlalchemy\_which\_should/](https://www.reddit.com/r/FastAPI/comments/1p0s8sm/async_vs_sync_in_fastapi_sqlalchemy_which_should/)
