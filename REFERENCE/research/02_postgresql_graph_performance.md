

# **Performance Architecture of PostgreSQL for Directed Graph Storage and Traversal**

The increasing prevalence of highly interconnected data in modern applications necessitates a rigorous evaluation of the underlying database architecture to support graph-like queries. While specialized graph databases have emerged to address these needs, the maturity and operational robustness of PostgreSQL make it a compelling candidate for consolidated workloads. To determine whether PostgreSQL can meet the demanding performance targets of sub-millisecond node lookups and sub-ten-millisecond graph traversals at a depth of ten for datasets exceeding 100,000 nodes, one must analyze the engine's internal execution models, the efficiency of its indexing structures, and the impact of its concurrency management system.1

## **Architectural Foundations of Relational Graph Modeling**

The representation of a directed graph within a relational framework traditionally utilizes two primary tables: a nodes table and an edges table. The nodes table stores unique identifiers and associated metadata, often utilizing the JSONB data type to accommodate the heterogeneous nature of graph entities.1 The edges table establishes relationships via foreign keys, defining the directionality of the graph through source\_id and target\_id columns. This structure leverages the proven efficiency of B-Tree indexing for primary and foreign key lookups, providing a stable foundation for the adjacency list model.1

The performance of this model is fundamentally tied to the query planner's ability to minimize the search space. In a directed graph with ![][image1] vertices and ![][image2] edges, a single-step traversal is an index-seek operation on the edges table. For a graph with 100,000 nodes and 500,000 edges, the average out-degree is five. This relatively low branching factor suggests that the search space expands at a manageable rate, provided the traversals are bounded.6

| Component | Implementation Detail | Performance Implication |
| :---- | :---- | :---- |
| Node Identification | Primary Key (BIGINT or UUID) | Sub-millisecond B-Tree lookup 8 |
| Relationship Storage | Normalized Edges Table | ![][image3] seek for neighbors 7 |
| Property Storage | JSONB Binary Format | Decomposed access without full parse 9 |
| Traversal Logic | Recursive CTEs | Iterative working table in memory 1 |

The choice between a normalized relational column and a JSONB property for node attributes depends on the access pattern. While JSONB offers flexibility, it introduces a serialization overhead. When a JSONB document exceeds the internal threshold of approximately 2,032 bytes, PostgreSQL utilizes the The Oversized-Attribute Storage Technique (TOAST), moving the data out-of-line.9 Accessing TOASTed data requires additional I/O operations, which can degrade the p99 latency of node lookups by a factor of five or more compared to inline data.9

## **Recursive Execution Mechanics and the Working Table**

PostgreSQL implements graph traversals using the WITH RECURSIVE syntax, which relies on a specialized execution model. The engine initializes a "working table" with the results of the non-recursive term. In each iteration, it joins the current contents of the working table with the edges table, producing a new result set that becomes the input for the next iteration.1 This process continues until an iteration produces no new rows, a state known as the termination condition.1

For a traversal of depth ![][image4] with an average branching factor ![][image5], the total number of rows processed by the engine is given by the summation ![][image6]. At a depth of ten with a branching factor of three, the engine evaluates approximately 88,572 rows.6 The latency of this operation is primarily determined by the speed of the index-nested loop join between the working table and the edges table.4

### **Depth-Specific Performance Analysis**

Empirical data from large-scale graph searches indicates a predictable latency curve as depth increases. On massive datasets, such as those exceeding 10 billion edges, PostgreSQL can maintain millisecond-level responses for shallow searches by employing "Tier Control," which limits the number of results returned at each level of the recursion.6

| Traversal Depth | Latency (p99) | Dataset Characteristics | Optimization Used |
| :---- | :---- | :---- | :---- |
| 1 (Direct Neighbor) | 0.46 ms | 100k+ Nodes | Primary Key Index 8 |
| 3 (Social Network) | 3.245 ms | 10 Billion Edges | Limit 100 per Tier 6 |
| 4 (FoF Search) | 1.614 ms | Social Graph | B-Tree Joins 4 |
| 5 (Broad Search) | 9 \- 120 ms | 12 Million Rows | Standard Recursive CTE 6 |
| 10 (Deep Traversal) | 150 \- 600 ms | 100k+ Nodes | Unconstrained BFS 13 |

The target of sub-10ms traversals at a depth of ten is aggressive for unconstrained searches. Without tier limits, the cumulative latency of ten successive index seeks and the overhead of managing the working table typically push the p99 response time into the triple-digit millisecond range.4 However, when queries are bounded by specific business logic—such as finding the top N most relevant neighbors at each hop—PostgreSQL successfully meets the sub-10ms requirement.6

### **Scaling Dynamics from 10K to 1M Nodes**

The performance of graph traversals in PostgreSQL exhibits a logarithmic relationship with the total table size but a linear relationship with the number of edges retrieved.7 As the graph grows from 10,000 to 1,000,000 nodes, the primary performance inhibitor is not the B-Tree depth (which only increases by one or two levels) but the "Buffer Cache Hit Ratio".16

For a 100,000-node graph, the relevant indexes for vertices and edges typically fit within the shared\_buffers, allowing for purely memory-bound operations.16 As the dataset reaches 1,000,000 nodes, the index size may exceed the allocated RAM, forcing the engine to perform random disk I/O.14 Research into warm cache versus cold cache performance shows that warm cache searches can be 40-60% faster, as they bypass the disk read API.15

## **JSONB Indexing and Property Lookup Efficiency**

The prompt's requirement for sub-millisecond node lookups is well within the capabilities of PostgreSQL's B-Tree indexing on primary keys, which frequently achieves p99 latencies below 0.5 ms.3 However, the use of JSONB for node properties introduces a different set of trade-offs regarding index types and lookup speed.

### **GIN vs. B-Tree Performance**

Generalized Inverted Indexes (GIN) are the standard for querying semi-structured data within JSONB columns.21 While GIN indexes provide flexibility for complex containment queries (@\>), they are significantly slower to update and larger in size than B-Trees.13

1. **jsonb\_ops**: This is the default GIN operator class. It indexes every key and value in the JSON document. While versatile, it suffers from high maintenance costs and larger storage footprints.13  
2. **jsonb\_path\_ops**: This operator class is specialized for containment queries. It hashes the entire path to a value, resulting in much smaller indexes and faster lookup times.13

Case studies from production systems like Notion highlight the magnitude of this difference. By migrating from jsonb\_ops to jsonb\_path\_ops, Notion achieved a 733% performance improvement on property-heavy queries.13 Despite this, GIN lookups rarely match the sub-millisecond performance of a B-Tree lookup on a normalized column. For performance-critical graph properties, extracting those fields into a standard relational column is the most effective strategy to ensure sub-millisecond access.3

### **TOAST and the Variable Length Limit**

PostgreSQL's storage manager attempts to pack at least four tuples into an 8 KiB page, leading to a target row size of approximately 2 KiB.9 If a JSONB property expands beyond this, the engine employs TOAST to move the attribute to a separate storage area.9

| Storage Mode | Latency Multiple | Mechanism |
| :---- | :---- | :---- |
| Inline Uncompressed | 1x | Direct page access 9 |
| Inline Compressed | 2x | CPU-bound decompression 9 |
| External (TOAST) Uncompressed | 5x | Additional I/O fetch 9 |
| External (TOAST) Compressed | 10x | I/O fetch \+ decompression 9 |

This mechanism represents a significant risk for the p99 latency target. A single node lookup that hits a TOASTed attribute can easily spike from 0.5 ms to 2.5 ms, violating the sub-millisecond requirement.9

## **High-Concurrency Orchestration and Connection Management**

Maintaining a concurrent load of 100+ queries per second requires an architecture that minimizes the overhead of PostgreSQL's process-per-connection model.16 Each connection consumes significant memory and induces context switching, which can lead to "thrashing" under high load.18

### **Connection Pooling Strategy**

The use of an external connection pooler like **PgBouncer** is essential for achieving the stated throughput targets.3 By maintaining a pool of persistent connections and multiplexing client requests, PgBouncer reduces the connection establishment latency, which can otherwise account for a significant portion of the total response time.18

For graph workloads, the following configuration guidelines are recommended:

* **Transaction Pooling**: This mode allows the same database connection to be shared among multiple clients after each transaction completes. It is ideal for the high-frequency, short-duration queries typical of graph node lookups.16  
* **Shared Buffers**: Allocating 25% of total RAM to shared\_buffers ensures that the most frequently traversed edges and node indexes remain in memory.17  
* **Work Memory**: The work\_mem parameter must be carefully tuned. Since it is allocated per operation, a recursive CTE with multiple joins can consume ![][image7] per connection. Setting this too high can lead to Out-Of-Memory (OOM) errors during peak concurrent loads.17

Tests simulating "Black Friday" traffic levels demonstrate that while simple SELECT queries maintain stable p50 latencies (12 ms), p95 latencies can spike to 45 ms if connection limits are reached.26 To keep the p99 traversal latency under 10 ms at 100+ QPS, the database must be over-provisioned to ensure that CPU utilization remains below 70%, preventing the queueing effects that drive tail latency.27

## **Comparative Performance: PostgreSQL vs. Specialized Graph Engines**

The decision to use PostgreSQL for graph storage involves a trade-off between the native adjacency of graph databases like Neo4j and the relational robustness of PostgreSQL.2

### **Neo4j and Native Adjacency**

Neo4j utilizes "index-free adjacency," where nodes contain direct physical pointers to their neighbors.2 This allows Neo4j to perform hops with ![][image8] complexity, whereas PostgreSQL must perform ![][image3] index seeks for every hop.7

| Metric | PostgreSQL \+ CTE | Neo4j (Native) | Apache AGE (Extension) |
| :---- | :---- | :---- | :---- |
| Traversal (1-2 hops) | Faster (Low overhead) | Moderate | Moderate 4 |
| Traversal (5+ hops) | Slower (Join overhead) | Faster (Pointer chasing) | Moderate 29 |
| Data Ingestion | Extremely Fast | Slow (Relationship creation) | Moderate 32 |
| Resource Needs | Memory-efficient | High RAM / High I/O | Memory-efficient 29 |
| SQL Interop | Native | Limited | Hybrid 5 |

Benchmarks comparing PostgreSQL to Neo4j show that for shallow traversals (1-3 hops), PostgreSQL often outperforms Neo4j due to the superior engineering of its query planner and the lower overhead of its B-Tree implementation on small datasets.8 However, as the traversal depth reaches ten or more, the cumulative cost of the relational joins begins to exceed the cost of Neo4j's pointer-chasing, particularly on datasets with high edge density.29

### **Apache AGE and the Evolution of SQL/PGQ**

Apache AGE is a PostgreSQL extension that implements the Cypher query language, allowing users to run graph queries within the relational engine.4 While AGE provides an expressive syntax, performance tests have shown that standard SQL recursive CTEs can be up to 40 times faster for precise, depth-controlled traversals.4 This suggests that the relational engine's B-Tree optimization remains the most performant path for structured graph queries in PostgreSQL.4

The industry is currently moving toward the **SQL/PGQ** (Property Graph Queries) standard, which has been integrated into PostgreSQL 17 and 18\.2 This allows for the definition of "Property Graphs" over existing tables and the use of the GRAPH\_TABLE operator.2 Early analysis of PostgreSQL 17 indicates significant improvements in CTE performance, including the ability to propagate column statistics from subqueries to the outer query planner, which helps avoid the "optimization fence" issues that plagued earlier versions.36

## **Production Case Studies: Notion and GitLab**

The viability of PostgreSQL for large-scale graph data is confirmed by its adoption in major production environments where relationships and hierarchical data are central to the product.13

### **Notion's Sharding Architecture**

Notion serves as a workspace for interlinked blocks, essentially a massive directed graph. As their user base grew, they faced a "scaling wall" that required a transition from a monolithic database to a sharded architecture.13

* **Strategy**: Notion implemented database sharding based on Workspace ID.38 This ensured that all blocks (nodes) belonging to a single workspace resided on the same shard, effectively localizing the graph traversal and avoiding the latency penalties of cross-shard joins.38  
* **Result**: This approach allowed Notion to maintain consistent performance as they scaled to millions of users, proving that horizontal scaling of the relational model is a viable path for large graph storage.13

### **GitLab's Database Scalability**

GitLab manages complex relationships between users, projects, and permissions on a monolith architecture supported by a 12 TiB PostgreSQL database.39 To maintain performance at a throughput of 60,000 transactions per second, GitLab employs rigorous testing using "thin-cloning" to validate the performance of new indexes and recursive queries against production-like data states.39 Their experience underscores the importance of monitoring and "Virtual DBA" tools in identifying query bottlenecks before they manifest as production outages.39

## **Scaling Analysis: From 10K to 1M Nodes**

The transition through orders of magnitude in node count exposes different architectural bottlenecks. At 10,000 nodes, almost any reasonably indexed query will be sub-millisecond.8 At 100,000 nodes, the system enters a phase where index density and buffer cache management become the dominant factors.16

1. **10,000 Nodes**: The B-Tree index for 50k edges is only a few megabytes. The entire database fits in the CPU's L3 cache or the OS page cache. Latency is negligible.8  
2. **100,000 Nodes**: The edges table index grows to several hundred megabytes. If the branching factor is low, traversals remain fast. At this scale, the 10ms traversal target is achievable if the branching factor ![][image5] is ![][image9].6  
3. **1,000,000 Nodes**: The indexes for a 1M-node graph with 5M edges can reach 1-2 GB. If shared\_buffers is under-allocated, the database will begin to experience disk I/O wait times.14 Traversals to depth ten may see latencies climb to 50-200ms as page faults occur.13

### **The Role of UUIDs vs. Integers**

The choice of ID type significantly impacts index density. BIGINT (8 bytes) allows for denser index pages compared to UUID (16 bytes). In a graph with 1,000,000 edges, using UUIDs can double the index size, potentially pushing it out of the buffer cache sooner and increasing traversal latency.4

## **GO/NO-GO Assessment and Risk Mitigation**

The evaluation of PostgreSQL as a primary graph storage backend results in a conditional **GO** recommendation, based on the following synthesis of research data and system limitations.

### **Target Validation**

PostgreSQL can meet the requirement for **sub-millisecond node lookups by ID** with high consistency.3 It can also meet the **sub-10ms traversal target at depth ten**, but only under the condition that the search is bounded by tier limits or a low branching factor.6 Unconstrained breadth-first searches on highly connected graphs will likely fail the 10ms p99 target due to the cumulative cost of relational joins and the expansion of the working set.4

### **Risk Assessment**

| Risk Factor | Impact | Mitigation Strategy |
| :---- | :---- | :---- |
| **Supernodes** | Exponential latency spike | Implement tier limits (e.g., LIMIT 100\) per recursion level 6 |
| **TOASTing** | Violation of \<1ms lookup | Keep primary properties in normalized columns; use JSONB for overflow only 9 |
| **Index Bloat** | Degradation over time | Aggressive autovacuum and periodic REINDEX CONCURRENTLY 21 |
| **Write Amplification** | Update latency | Use partial indexes and avoid over-indexing unused JSONB keys 21 |
| **Cache Misses** | p99 tail explosion | Size shared\_buffers to accommodate 110% of total index size 16 |

### **Optimization Checklist**

1. **Mandatory Indexing**: Primary key on nodes.id and a composite index on edges(source\_id, target\_id). The latter is critical to enable index-only scans during recursion.7  
2. **JSONB Operator Choice**: Use jsonb\_path\_ops for all GIN indexes unless key-existence queries are specifically required.13  
3. **Concurrency Layer**: Deploy PgBouncer in transaction mode and tune max\_connections to match the physical core count of the server to minimize context switching.16  
4. **Memory Tuning**: Allocate sufficient work\_mem to prevent the recursive joins from spilling to disk, while ensuring shared\_buffers is large enough to pin the adjacency list in memory.17  
5. **Query Engineering**: Incorporate cycle detection (using an array of visited IDs) and depth counters in all recursive CTEs to prevent runaway executions.11

PostgreSQL represents a "pragmatic" graph database solution. It offers the benefit of a mature ecosystem and ACID compliance while providing performance that rivals specialized graph engines for the majority of production use cases involving bounded traversals and high-concurrency node access.2 For applications that do not require complex, unconstrained graph global algorithms (like full-graph PageRank), PostgreSQL with an optimized indexing strategy and connection pooling is an excellent choice for a production graph storage backend.

#### **Works cited**

1. Graph Algorithms in a Database: Recursive CTEs and Topological Sort with Postgres, accessed February 17, 2026, [https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/](https://www.fusionbox.com/blog/detail/graph-algorithms-in-a-database-recursive-ctes-and-topological-sort-with-postgres/620/)  
2. Working with Graph Data in Neo4j, PostgreSQL, and Oracle \- Baremon, accessed February 17, 2026, [https://www.baremon.eu/graph-databases-in-practice/](https://www.baremon.eu/graph-databases-in-practice/)  
3. PERFORMANCE BENCHMARK POSTGRESQL / MONGODB \- EDB, accessed February 17, 2026, [https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL\_MongoDB\_Benchmark-WhitepaperFinal.pdf](https://info.enterprisedb.com/rs/069-ALB-339/images/PostgreSQL_MongoDB_Benchmark-WhitepaperFinal.pdf)  
4. PostgreSQL Showdown: Complex Joins vs. Native Graph Traversals ..., accessed February 17, 2026, [https://medium.com/@sjksingh/postgresql-showdown-complex-joins-vs-native-graph-traversals-with-apache-age-78d65f2fbdaa](https://medium.com/@sjksingh/postgresql-showdown-complex-joins-vs-native-graph-traversals-with-apache-age-78d65f2fbdaa)  
5. PostgreSQL Graph Database: Everything You Need To Know \- PuppyGraph, accessed February 17, 2026, [https://www.puppygraph.com/blog/postgresql-graph-database](https://www.puppygraph.com/blog/postgresql-graph-database)  
6. Implementing Graph queries in a Relational Database | by Ademar ..., accessed February 17, 2026, [https://blog.whiteprompt.com/implementing-graph-queries-in-a-relational-database-7842b8075ca8](https://blog.whiteprompt.com/implementing-graph-queries-in-a-relational-database-7842b8075ca8)  
7. Demonstrating PostgreSQL Database Indexing Performance at Scale | by Robin Viktorsson | Jan, 2026 | Level Up Coding, accessed February 17, 2026, [https://levelup.gitconnected.com/demonstrating-postgresql-database-indexing-performance-at-scale-96f39a6c7031](https://levelup.gitconnected.com/demonstrating-postgresql-database-indexing-performance-at-scale-96f39a6c7031)  
8. Graph-Vector Database Performance Benchmarks (2025) \- HelixDB, accessed February 17, 2026, [https://docs.helix-db.com/benchmarks/v1](https://docs.helix-db.com/benchmarks/v1)  
9. Postgres large JSON value query performance (evanjones.ca), accessed February 17, 2026, [https://www.evanjones.ca/postgres-large-json-performance.html](https://www.evanjones.ca/postgres-large-json-performance.html)  
10. Select large amount of data with text or jsonb is slow : r/PostgreSQL \- Reddit, accessed February 17, 2026, [https://www.reddit.com/r/PostgreSQL/comments/1j4vtov/select\_large\_amount\_of\_data\_with\_text\_or\_jsonb\_is/](https://www.reddit.com/r/PostgreSQL/comments/1j4vtov/select_large_amount_of_data_with_text_or_jsonb_is/)  
11. PostgreSQL Graph Search Practices \- 10 Billion-Scale Graph with Millisecond Response, accessed February 17, 2026, [https://www.alibabacloud.com/blog/postgresql-graph-search-practices---10-billion-scale-graph-with-millisecond-response\_595039](https://www.alibabacloud.com/blog/postgresql-graph-search-practices---10-billion-scale-graph-with-millisecond-response_595039)  
12. Graph Queries in PostgreSQL \- EDB, accessed February 17, 2026, [https://info.enterprisedb.com/rs/069-ALB-339/images/Q4%202021%20-%20Webinar%20-%20Slides%20-%20Graph%20Queries%20in%20PostgreSQL.pdf](https://info.enterprisedb.com/rs/069-ALB-339/images/Q4%202021%20-%20Webinar%20-%20Slides%20-%20Graph%20Queries%20in%20PostgreSQL.pdf)  
13. Customer Story: How Notion Runs PostgreSQL at Scale on Amazon ..., accessed February 17, 2026, [https://pganalyze.com/customers/how-notion-runs-postgres-at-scale-on-amazon-rds](https://pganalyze.com/customers/how-notion-runs-postgres-at-scale-on-amazon-rds)  
14. PostgreSQL Stories: From slow query to fast—via stats | Render Blog, accessed February 17, 2026, [https://render.com/blog/postgresql-slow-query-to-fast-via-stats](https://render.com/blog/postgresql-slow-query-to-fast-via-stats)  
15. Performance Benchmarking of PostgreSQL 17.5-1 Using a Java Object Model, accessed February 17, 2026, [https://rootrql.com/docs/brief/benchmarkingPostgreSQL\_17\_5\_1.html](https://rootrql.com/docs/brief/benchmarkingPostgreSQL_17_5_1.html)  
16. Outgrowing Postgres: Handling increased user concurrency \- Tinybird, accessed February 17, 2026, [https://www.tinybird.co/blog/outgrowing-postgres-handling-increased-user-concurrency](https://www.tinybird.co/blog/outgrowing-postgres-handling-increased-user-concurrency)  
17. Key metrics for PostgreSQL monitoring | Datadog, accessed February 17, 2026, [https://www.datadoghq.com/blog/postgresql-monitoring/](https://www.datadoghq.com/blog/postgresql-monitoring/)  
18. How to Optimize PostgreSQL for High Traffic and Concurrent Users \- DEV Community, accessed February 17, 2026, [https://dev.to/nilebits/how-to-optimize-postgresql-for-high-traffic-and-concurrent-users-1j8a](https://dev.to/nilebits/how-to-optimize-postgresql-for-high-traffic-and-concurrent-users-1j8a)  
19. Outgrowing Postgres: How to run OLAP workloads on Postgres \- Tinybird, accessed February 17, 2026, [https://www.tinybird.co/blog/outgrowing-postgres-how-to-run-olap-workloads-on-postgres](https://www.tinybird.co/blog/outgrowing-postgres-how-to-run-olap-workloads-on-postgres)  
20. GoREST turn any database to a production grade REST API \- DEV Community, accessed February 17, 2026, [https://dev.to/nicolasbonnici/from-a-database-to-a-rest-api-3cgf](https://dev.to/nicolasbonnici/from-a-database-to-a-rest-api-3cgf)  
21. PostgreSQL Performance: Essential Indexing Guidelines \- DEV Community, accessed February 17, 2026, [https://dev.to/shrsv/postgresql-performance-essential-indexing-guidelines-1i90](https://dev.to/shrsv/postgresql-performance-essential-indexing-guidelines-1i90)  
22. PostgreSQL Index Best Practices for Faster Queries \- Mydbops, accessed February 17, 2026, [https://www.mydbops.com/blog/postgresql-indexing-best-practices-guide](https://www.mydbops.com/blog/postgresql-indexing-best-practices-guide)  
23. MongoDB vs PostgreSQL: Choosing the Right Database in 2026 \- Koder.ai, accessed February 17, 2026, [https://koder.ai/blog/mongodb-vs-postgresql-choosing-the-right-database](https://koder.ai/blog/mongodb-vs-postgresql-choosing-the-right-database)  
24. Postgres Performance Issues and How to Scale Enterprise Databases \- SingleStore, accessed February 17, 2026, [https://www.singlestore.com/blog/postgres-performance-issues-and-how-to-scale-enterprise-databases/](https://www.singlestore.com/blog/postgres-performance-issues-and-how-to-scale-enterprise-databases/)  
25. PostgreSQL: Network latency does make a BIG difference, accessed February 17, 2026, [https://www.cybertec-postgresql.com/en/postgresql-network-latency-does-make-a-big-difference/](https://www.cybertec-postgresql.com/en/postgresql-network-latency-does-make-a-big-difference/)  
26. PostgreSQL vs MySQL for Spring Boot: Same App, Different Results \- Stackademic, accessed February 17, 2026, [https://blog.stackademic.com/postgresql-vs-mysql-for-spring-boot-same-app-different-results-2439223b4fbc](https://blog.stackademic.com/postgresql-vs-mysql-for-spring-boot-same-app-different-results-2439223b4fbc)  
27. JSONB Is Not BSON: How PostgreSQL Falters With Update-Heavy Workloads | MongoDB, accessed February 17, 2026, [https://www.mongodb.com/company/blog/techincal/jsonb-is-not-bson-how-postgresql-falters-with-update-heavy-workloads](https://www.mongodb.com/company/blog/techincal/jsonb-is-not-bson-how-postgresql-falters-with-update-heavy-workloads)  
28. Best Vector Databases in 2025: A Complete Comparison Guide \- Firecrawl, accessed February 17, 2026, [https://www.firecrawl.dev/blog/best-vector-databases-2025](https://www.firecrawl.dev/blog/best-vector-databases-2025)  
29. Postgres vs Neo4j – Comparing Fundamentals | pgbench.com, accessed February 17, 2026, [https://pgbench.com/comparisons/postgres-vs-neo4j/](https://pgbench.com/comparisons/postgres-vs-neo4j/)  
30. Graph Databases: When relationships matter more than rows \- Baremon, accessed February 17, 2026, [https://www.baremon.eu/graph-databases-when-relationships-matter/](https://www.baremon.eu/graph-databases-when-relationships-matter/)  
31. Can Neo4j Replace PostgreSQL in Healthcare? \- PMC, accessed February 17, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC7233060/](https://pmc.ncbi.nlm.nih.gov/articles/PMC7233060/)  
32. How does the performance of a graph database such as Neo4j compare to the performance of a relational database such as Postgres? \- Washington, accessed February 17, 2026, [https://courses.cs.washington.edu/courses/csed516/20au/projects/p06.pdf](https://courses.cs.washington.edu/courses/csed516/20au/projects/p06.pdf)  
33. Apache AGE vs Neo4j: Battle of the Graph Databases \- DEV Community, accessed February 17, 2026, [https://dev.to/pawnsapprentice/apache-age-vs-neo4j-battle-of-the-graph-databases-2m4](https://dev.to/pawnsapprentice/apache-age-vs-neo4j-battle-of-the-graph-databases-2m4)  
34. Good Graph Database options? \- Reddit, accessed February 17, 2026, [https://www.reddit.com/r/Database/comments/1fit1ix/good\_graph\_database\_options/](https://www.reddit.com/r/Database/comments/1fit1ix/good_graph_database_options/)  
35. Representing graphs in PostgreSQL with SQL/PGQ \- EDB, accessed February 17, 2026, [https://www.enterprisedb.com/blog/representing-graphs-postgresql-sqlpgq](https://www.enterprisedb.com/blog/representing-graphs-postgresql-sqlpgq)  
36. PostgreSQL 17 \- A Major Step Forward in Performance, Logical Replication and More, accessed February 17, 2026, [https://www.pgedge.com/blog/postgresql-17-a-major-step-forward-in-performance-logical-replication-and-more](https://www.pgedge.com/blog/postgresql-17-a-major-step-forward-in-performance-logical-replication-and-more)  
37. Postgres 17 Query Performance Improvements \- Microsoft Community Hub, accessed February 17, 2026, [https://techcommunity.microsoft.com/blog/adforpostgresql/postgres-17-query-performance-improvements/4284693](https://techcommunity.microsoft.com/blog/adforpostgresql/postgres-17-query-performance-improvements/4284693)  
38. Database Sharding with PostgreSQL: A Case Study of Notion's Implementation \- Talent500, accessed February 17, 2026, [https://talent500.com/blog/notion-postgresql-database-sharding/](https://talent500.com/blog/notion-postgresql-database-sharding/)  
39. Database Lab: How GitLab iterates on SQL performance optimization workflow to reduce downtime risks | PostgresAI, accessed February 17, 2026, [https://postgres.ai/resources/case-studies/gitlab](https://postgres.ai/resources/case-studies/gitlab)  
40. PostgreSQL 17 Log Analysis Made Easy: Complete Guide to Setting Up and Using pgBadger | by Jeyaram Ayyalusamy | Medium, accessed February 17, 2026, [https://medium.com/@jramcloud1/postgresql-17-log-analysis-made-easy-complete-guide-to-setting-up-and-using-pgbadger-befb8e453433](https://medium.com/@jramcloud1/postgresql-17-log-analysis-made-easy-complete-guide-to-setting-up-and-using-pgbadger-befb8e453433)  
41. Advanced PostgreSQL Indexing: Multi-Key Queries and ..., accessed February 17, 2026, [https://frontendmasters.com/blog/advanced-postgresql-indexing/](https://frontendmasters.com/blog/advanced-postgresql-indexing/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAXCAYAAAAC9s/ZAAABUElEQVR4AdySvUoDQRSFR0FFCy3EQgv/G1/Axs7GQixEESx8ATtfwE5EEEQQSzsFBdFWBLGxEiux0MY/LLQxBFKF/HwnZMLdSXYTSBMSzjfn3uydw87udromf60TMM5JJmHC0EdtNUIzBZoTA9TOH2GX5hTu4RoOYAastmhu4RKOYR4qAes02jSKv8EyPIHVDs0vnMAaXEElQPWrFhiEAlh10CzBIxxBGkryR1DzzZKHMQg1zR8rsAeRcBvwz0UlD+Pd4NVLsQln8AMR2QAlf3FVG4Zwr0WKHiidGY/IBujChxbQa8WcfNU5dwhZqFIY8Fme0HPootat3+D+AVNGlRSwwGg/XECs4gJm2bEB+mAyeKzCAP8M5thxB8+QqDDgnWm9jQf8HFRj8QoDUozuwzaoxpIVBuQYV8AL3pDCAG36Y9EnjdVXrYD6u8xEGwQUAQAA//+0NeKeAAAABklEQVQDAHWwNi8NEGn8AAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAZCAYAAADuWXTMAAABbElEQVR4AeySzytEURTHr1+lycJSEfm5kY0fO2RhhRQWUvIHWFpZyc5C2doIZWNhyRKFUiILRSzQTFhSimYzM5/vvPfqzn1vMT9207zO537vOeedd+8991WbEp4yKR6gBed5MuWe+Z7CGfiDMdiDaZiAWViGBCgXc4tTJH6gC9JwBL/wD9/wBEvwCgm3mJhpYuiGW9AOkJA9E4lHFQ+TqIILCEzvnQQO2gBfCqI5Nup7l75KFhjiENgkk1RU8QgJ2SrDKdzALtgfUx+MW9zIS32gxqyg67ANdWAX45pQsc5bQ0YrXqMq2EcfQFeEmF6GOQgVB1u+UtJiw5rrOO/y3W2rWbpfu1j+oV6GTtA13qE5K8cIDMIbfIBrup4dgmoe4p25npm+uIjWwiPI7/C1B52HFxiCA8iatj3O7AzW4BP6QT+ImiVVbpNYErZAvyrirXzMrA1aoDkCxVuJt4MWQDzTyt6siLFSXGDTMgAAAP//wEVZWQAAAAZJREFUAwBIaEgzKXYlPwAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEYAAAAYCAYAAABHqosDAAAFh0lEQVR4AeyYZ6geRRSGN/besSsqigVUVFTsBnsXVPSHXSzYEOx/7IpdEURRsSB2LNhISO+dJCQhCQkkJIGE9F5IfZ7NzmZnv918yb0JfIFc3nfPzJnZ+WbPnDlz5u6QbP+rtMB2w1SaJUm2hmEO4Lf2gK2OQ5jgzrASzQyzG29dAq+Hh8NmsM/vdCr+4C7UD4KthhOZ0C9wR9iAOsP40t/0/hdqmLOR3WFnqKURDdgVzc/wWbgAHgnnwhVwCGw19GZCzusTZAPKhulAjxdhL/glvBy+Bl+GZ8Dd4UC4FyzjTRSj4FAopvHQiIOQrYp3mdhV8AoYoWyYD2l9Cd4I/4FFLKOi0Y5BPg2L2JfKg7Bs/ZXopsJWxWom5pxfR0YoGuZmWp6Cb8DBsAp6w1oaboBF3EtlfEZEhDVRrfUqbv9zmZY7ArEewTD7Uf0UzocfwzpoYQ1zfKnDrdT7wyrYv0rvtryJhsfgRdBtjIiwEzUnbL/DKO8Dn4R6J6IBe6LR241vFBMD65kUfP9gZBVmopwAL4M5gmHuR+OJ8iNyCazD0TT4jgaimMIfd/J6U6rYhMf59BkDT4CT4N2wCzQmIVIcx9OYpSFOomxsM2DqgV9QPxAW4bxc/QtRjobGDU/IqylfAyfCk2EVnLuLk7c5mJVrfcBOcGO4IGscm0mFBnWltLz1ZjyCDv7O28j34f9QD3BBvqUcPOd7ysvhffCdjKcie8Cj4BxYhEHUU+YrlMY8jee4b1F/Bu4NyyEAVQrn7nekFR8axjwjWMuB1dcxDFwMzG5D+8/zsQl8jj5O8k9kEf9RcXXDXNwCnmyoU1h2vmdRs4yIoMF/QmNqgUiMe7OS9X9uQ0umEcoynXuUa/lDrpB7WRcNA5VftO4edf86uKuiTmpYpaurbEY/zD7mOMrAxVkhtPelfiwMcGu5heuOf+dkrLiUF5yj71NM4bay0NNHBc21omxdw6icTGfLxYwVVQRzGZM4E7iiG4cP1H2jF2oqLoBN0URQuDiIJMzBD3Wl3VLv0fA8vAt6+iFqoWH60KoRESlu42ncqXvXuS+kTw6NYSVYN6yWuiKvo/II/Bya+CFyzM5K+2eyLPwNvTLoDaCWjRPKwFDvlilMHzomSfIBdbedJ6FbhWotPI3sZ4IaOmnci6l4sGj07yiXYTiIdouTttMLPNxneoWnDNUct1Ay2pslPk65jEUo3PNOiGID3Gp6QzCOHzqFXk/AADNpveEHFMOg0JPNuo0Znl7e186hwbEQldAANnh9UcrzePidXnHuoDwSluHchxeVvmB9Og+j+qFI8xGPSLNbV+9hdB53Zr1F90Sdw34ewbmCgke7e74jZfMPj2U/zgXwSLV9AG3fwH7QiXsCUUxhgDf/8HTxtHJxjC/jaPUuh2jAaWjMtEcgAzxQ9Gq/R8OZr4U2pY5gghd2jbro3w4O4FZ6lBYn7wQeoHwljF6iXoYniqdJcTX1Clfa/athvEp4KfVdJ+/29JTzKHZVPa28Qth+Cg9d3qCpx+lt3vT9AGPBR7RXwaPZbwhxzD7+lr9t2v8QCj0RkcP+Hhx/5BoKwWMopnBiurIBz481KKcNTR4OakB22zXpGjW7ki7A0kibJN7oZ6DrCp0TIvGDvKpoMF1fXZkaLYoVWQdzJD22Kgs389YrHT/rnkQekyvbUHCLGac8sXTNNgwRvfIbNQOlp5GBkWrSgYce5H2uzmPoslkwHdBbG65BZY/ZrFFLnY0Jf6F7BbYXetLpDOKW/hXpdUHeSdnrw2fI9sIt+jWD3A79PcQGbEnDOKo381UUoiySelvghdaYYYzTU/zf0D0MZI6CaDfMsr2SRKdRGHVLG8ZxX+XRsALoWg2egsbRynltDcNU/tC2plwHAAD//4iXlq8AAAAGSURBVAMAvHr3MbKDAIoAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAYCAYAAADDLGwtAAABGElEQVR4AdTRv0qCURjH8ZegIqIlimppqAso+kdNtYa3ILgIingD6qyTDk7i7DWIi4iiOOikg7g46ao4iaCo39+BIw7y6ibK8znnOccf5z2vnjh7fg4TPOd2126P/iUwxhR5t2CFwBNUNbegAu8aUNkV/CO0wNYT3/jCgyso2GIeb574yEYVfrygiE+U4djgAwuFOswhJFDCKfRS62CcjXtEYWtOo/vpABO8Y8OHBoawpd+xzWIEE3yl0RXMXehVFwxfMI9lNsFLNajD1g+N/joFv+mDOkmP1H1u2FDdMqSgajJ4UVdwQBNGBGnkoJfqMydxhraCzE6W4QMZ/KOAZ8QQgLmjZpkwdLGEasbQg1nbE1m71zEEVwAAAP//VBhoSwAAAAZJREFUAwDlEjEx3+Kq8gAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAXCAYAAADduLXGAAABQ0lEQVR4AcySu0pDQRCGj4KFhRZeQKxstBALr4UKor6ArSCIIFYiWgq+g42NdmIplqKd4AVMEVImZUggIYSEtLmT719ylg0bAiFNwnwzszN/ds+ZPaNBH7+BxdpgpNuBaoT1WZIlWIN58MwVH9N9hygcgWeu+IHuIzThDzxzxWru4nIQB89c8TjdHfiBOsgmcDNgzBWvUJmDL9A0NoiHcAYLELhiNbTjL409WAdN5pq4DZ64QFHjWyR+giaTJAornqSwCTW4hBLkIQJ3EAMr1nFTFN7gG87hBHSSHqtKbsUHLFS4Jz6B/nhBlG3hlsGK91kkIAvFNgRjp/gyGPEYySp8gG6PEOhRpkluQJeUJhpxg+QKdDzB2Av+FvRiz0SN1Ii12yuFFISm3fRR/VPIgLHwUipm1ek0RmGrodgWeiVDIm4BAAD//94S7+0AAAAGSURBVAMATW06LxFrUN0AAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD8AAAAaCAYAAAAAPoRaAAAEmklEQVR4AcyYd+gURxTHN72R/JGEVEISSEivpJBCCukNUkgjjRRCig27YsGCDUHsiorYFUXBiijYBRGxC3YUC6igoiJi/XzOm2M99+5+J+65x/c77+3s27l5OzNv3uzVUfq/d/iL5XAIzBRq4fx8PN4I18JMoRbO6/DbFAtgppCm8z/iaSfYFN4MszDy39OPB2AOwfmHuXoCPgmfgk/n+QyyLrwVuzh6cmF7bZG2txB5Bl5pfEMHroc5BOcnc7UBToL/wX+K+C/X/8NGsCucAFfDNXk6uqg5vEipvXao0TUUtZjyt/A/t8Fy+I6bW2EOwfnfuToBH4T9Yb08dViGF/In9Z9DZ8jdyFbwKPwVhrY+RV8Gj0NhtE/TeftmH2R44f5vnA9x0R3aN8R5hA6v4rIFdG2OR94EK2E/Bt3gS1D7t5DiCIWzAhE9S+GS2If8A6aBATT6FRRLLBLYkrpp0GWIOI/gvFd9KGZA17hrFrVOcBv7GUtHHxFNoXgeNoAGvT1I9anItPBKvuGkGXYd9wbBL+FcWEDc+bPUOv33Ip1K4W1yWRE26svTcCfFB3AsdFkYA9qhH4Bp4V0a3gJ3w2KcpGId/AmOhAXEnbfSqewIGpmHUlHYFtArwaUTbE6hBGeNJZKqVHADrb4O46PuGn+POoMtIvqQYhsU31rIYuetcxR7oNwOR8PQAGom4ZQ35gTnm9BL45fruzG6OERxDP4F3dkQUZTkvDecpkZsg1gbKzJMs0e7p/MdUNyypyOt96WgRkspHPHWyNMwh1LOu04MVoex8g2+icwq3EpdYs3p4Dw4C66EDuBAZIC+FBy3spTz3ttOYbLjtL9gf6Q+KzBbe43OKD9DGmjvRLrDmFobw7hMRjnnfcKH56C0h1mE693cxN3JGfA1nXS7RlRGOecf4/HO0MOAywA1qoaPY2w2iKgaRm9HtNKDxiRtPDbvQJkNzTGuQnrPjBQ1GaWcvwPzEfAXeBBeChyJe6t80P26N89MhB6uEGVhLIrv7zdibZ5hzqLj7lxUJSPJedfPOMzdLmwYtU64q8jKrKrarzcGrIa0sxnWBc9hFM8cx3DtFj0MaebpbEBNRpLzdlrn3TqSn7q41pS4X77aNk1nO3Lt9EOkhldp2UFC5LCI8hFojOqCLAs7GjewIQ8hw+OVFfR7uG/i4HEYNfqbYjE0Vhg3UCMDkvEj0EgsfUHuzV9odAncxTNmk4gCXKbWFypKKXHnTfxfxtBEAFER12Jhvuzbvg89RNkV6AZI198mdOHJy2Qp0NxBuhc7Sp64tIsz7VlTyPBe4F8d7fVI00M/TihND6V6M+7Z+V5IT24GFtNfp9lM6kwfEZFfan9DGQU9IyAi1+YbKKX4KPeKUTPn7awpoPumB4L36YmHgY+QUt16o6tbmKPqQUan5WDsApxNHnE9QYVZ5Jneryyl6OEkPB9kzZz385QZ0if888d56nScoV4badbnMzK+pbjNeCz+gXbcdxGRMcC0sxQ9cmpnAPNLkjPBbbYvlam9BEeJ9i8rdN7Y4fJw/VfTuIcpP5vdz0MukfpI20NcfpwDAAD//x1ArHYAAAAGSURBVAMAI9bbRnCS2k0AAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,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>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAYCAYAAACIhL/AAAADJElEQVR4AeSW2atOURiHzzFPZR4vpCihlOQCSSIyJvwBImNCSZEyxY0LSYmQGyUpMoaElCnTBWVKcqGUeUjI+Dyfvba999nfcPqOUk6/Z7/vetfaa7/f2mu9+zSq+cf//ssEO/BSWkGlasbAzpCrcivYgrtGwiToAeXkmIMMagqVqjED90M/qKNiCfZl5FE4DiY4BHsOTkNXyFNzgj5oOfYdZNWEwBLIru4nYgvAe+vMnU2wloEr4QLsgjGwHtbAIGgJV6ENZLWRwB24AUGu5EIam+ExbIHWkNVDAofAcZg/yibogNV0T4FjkJS/1OR7EVwGSbWlMQe2QlLO7zY5SfASlNJ2OqfCAIjlBKFh51IaG+Aa5MnV+UnHZEhqJo0HEZhYX/D80Wew76GUntN5HuZCrJBgOyLb4C34GjC5+k7UBPtgk5pB4zJUqytMMBpihQRnEfEE7sN+hGLqSYf3mChuQZ5C96erWwhUcbnOvb7ijtiCfJjOBC9wCkppeNR5L7Iaf5gb31dkuxrCHN3DJCZooRwRBfwFkZtrwt5LHiC3h4PfeKkAK0WxYW4x+1Ir6A3WqB/0vIBi6kKHp9satxs/yB+o/9lLBfi8YsPCHHGtdAU9aU+4Q9+6hZsra6HF2EL8KjHideRbaiK3pCmVYJgjPvEm5WwXvcBgyNNEgvNhB1jAMbFeRl77yJYzpRIMc8RvMiS4glndQ66Sp5JmrOl4foY2YRdBVh8IPIVs6SGUUtgKvoVUR6LRG9/5HmELCgk+ozUOuoH1bDHWr8VZ7DwYD35FkuWFUCzHDYtbaec2TYv4NKyvzk/lXXxLGyalobR8vucBt6YmJGjDE+wr9tvpat4nOBvGQtgCuLk6QdRK4GHDTWkgLf/5cH+Ji9Cf2B7IahSBnRArmaDBr1xuwl7woR4e3LLyQ+/BcTuUHVxkgMn5T8iRZH82wWRffXxfvfvYE57dw5XMU8ugcL9z0fythkrQ2Szeh3HWQn3lnr/FTQcgpYZM0In9T+gbTieoVH6J3Jer8m5o6AR9xjouoTbilpWfNytEfHKTd/yNBJPzV+3/AgAA//981Xc1AAAABklEQVQDAKLifzECH9stAAAAAElFTkSuQmCC>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAXCAYAAAAcP/9qAAAB/ElEQVR4AeyUSyhFURSGD3mXMCAjYsBATEwo5TEQIikGEqUwEBNlpDyGJhgoA4ZeKQlJkhAyETJEMlBKiYHyfnz/5dwo7t333rgTt//ba9991jrrrHX22YGWn37/if+s8b/Z6lqqKIAoCIJEaIIEsDxJHE1AB2xCGLhTAw4rcA0PcAqlcAFGieNx7IUFUHAe9g7c6RWHbdiFWaiGcnDEuqo4GachmIAtyIExeAITveBUA5lQAZOgh8FY31aczhUlGMROQT7MgTOIuYlc+n+uOJu7qSVd2H4ogVXwVkpcTPASrIGKSMU6ZCfO5d86zEMl7ICvUqvVZm0o7YtDbrgBeoXOVitpGotZsAxFEAC+qIXgRngEaZghFjrBmVjzIwZ9AvXYQtDDqHq7Kyx5JN1PVdtB5x8TfdtfEn+sW2dM2kA7URtN360eJoQ1U5XheAVVYOuZid57BPbbxFoXlwzaaKo+hrk60IoNB3fKwCESHEmwUhyDXt8e1mViXRc3DH2gDXKLnYZQcCUdNurU+CcnHSBqfY/WPHl/9wSMgD4zzZn+qH2uzICSd2MVp+O2jrnWjCrG1ysNEKUqj7HqUgpWBxPGciZW63TBhCRHpNlwgtsoLIL2DOZddqt1orSzZEowvj7JTnzAXfSxm9CMr30oMPVOdmLvon2I8lviNwAAAP//q2XMLwAAAAZJREFUAwCjgWIv9VGYTgAAAABJRU5ErkJggg==>