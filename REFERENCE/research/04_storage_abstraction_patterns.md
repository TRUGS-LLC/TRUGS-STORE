# **Architectural Design Patterns for Graph-Based Storage Abstraction Layers**

The design of a sophisticated storage abstraction layer represents a critical inflection point in the lifecycle of modern software architectures, particularly when dealing with non-linear data structures such as graphs. As systems evolve, the initial reliance on specific database technologies often becomes a bottleneck, necessitating a transition toward persistence ignorance. This architectural shift is fundamentally rooted in the Dependency Inversion Principle, which dictates that high-level business logic should remain decoupled from the volatile details of infrastructure.1 By establishing a clean, consistent interface for graph operations, architects can ensure that applications remain resilient to changes in the underlying storage medium, whether that involves transitioning from a relational database like PostgreSQL to a high-performance in-memory store or a decentralized, immutable ledger such as Hyperledger Fabric.3

The core challenge in building such a layer lies in balancing the need for a unified API with the distinct performance and consistency characteristics of diverse backends. An abstraction that is too thin risks exposing implementation details, creating a leaky abstraction that forces developers to account for backend-specific quirks within the domain layer.5 Conversely, an abstraction that is too thick may obscure the unique capabilities of a specific database, such as the rich query language of a graph-native store or the consensus-driven integrity of a blockchain.7 To navigate this landscape, the designer must employ proven patterns—such as the Repository and Adapter patterns—to define a protocol for node and edge manipulation that supports both synchronous and asynchronous execution models.3

## **The Foundations of Persistence Ignorance and the Repository Pattern**

The quest for a storage abstraction layer often begins with the Repository pattern, a classic architectural construct that mediates between the domain model and the data mapping layers.11 In the context of graph data, a repository functions as an abstraction over persistent storage that mimics the behavior of an in-memory collection of objects.1 This pattern is instrumental in Domain-Driven Design (DDD), where it is used to manage the lifecycle of aggregate roots.13 For a graph storage layer, the graph itself, or a specific transactional sub-graph, acts as the aggregate, and the repository provides the methods to add, retrieve, or query these entities without exposing the complexities of the underlying database engine.13

A primary benefit of the Repository pattern is the enablement of "pure" domain models that are blissfully unaware of persistence concerns.3 When implemented correctly, the domain model does not inherit from any database-specific classes, such as SQLAlchemy's declarative base.3 Instead, a mapping function is used to bind domain classes to database tables or objects, ensuring a clean separation of concerns.3 This decoupling facilitates the creation of "fakes" for testing, where an in-memory repository can replace a slow database backend, allowing for rapid and deterministic test execution.1

| Pattern Component | Role in Graph Abstraction | Implementation Example |
| :---- | :---- | :---- |
| **Abstract Interface** | Defines the "Port" through which the domain interacts with storage. | AbstractGraphRepository (ABC or Protocol) |
| **Concrete Adapter** | Implements the interface for a specific backend. | SqlAlchemyGraphRepository, InMemoryGraphRepository |
| **Domain Object** | Represents the graph entities (Nodes, Edges) without persistence logic. | Node(id, label, properties), Edge(src, dst, type) |
| **Unit of Work** | Manages transactional boundaries across multiple repository calls. | Context manager for database sessions or blockchain transactions |
| **Data Mapper** | Translates between domain objects and backend-specific data formats. | SQLAlchemy classical mapping or Pydantic serialization |

3

The effectiveness of a repository is often undermined by common anti-patterns, such as the "Generic Repository." While tempting to implement a single interface for all entities, this often results in a loss of meaningful contracts and forces the leaking of query-specific logic, such as pagination and sorting, into the domain layer.11 Furthermore, repositories should strictly return domain entities rather than Data Transfer Objects (DTOs) or ViewModels, as returning these artifacts creates a toxic coupling between the domain and the presentation layers.13

## **Defining the Graph Protocol: Structure and Traversal**

A robust graph storage abstraction must define a comprehensive protocol that covers both structural operations and complex traversals. The structure of a graph is fundamentally defined by its vertices (nodes) and the edges that connect them.17 In the Apache TinkerPop framework, which serves as a global standard for graph computing, the structure API exposes interfaces for Graph, Vertex, Edge, and Property.17 This model allows for a property graph where both nodes and edges can store arbitrary metadata in the form of key-value pairs.18

The protocol for a graph storage layer must define several essential operations. Structural methods such as add\_node and add\_edge allow for the incremental growth of the network.19 Inquiry methods, such as neighbors or has\_node, provide the basis for simple lookups and connectivity checks.19 However, the true power of a graph lies in its traversal—the ability to move across the network to uncover hidden relationships.17 A well-designed abstraction layer provides a functional data flow API, where a TraversalSource generates traversals that can be evaluated either as real-time database queries (OLTP) or as batch analytics (OLAP).17

| Operation Category | Standard Methods | Backend Implications |
| :---- | :---- | :---- |
| **Node Management** | add\_node, remove\_node, update\_node\_props | Handled via INSERT/DELETE in SQL or putState in Blockchain 16 |
| **Edge Management** | add\_edge, remove\_edge, get\_edge\_data | Requires adjacency verification and index updates 19 |
| **Adjacency Inquiry** | neighbors, adjacent, degree | Performance depends on index structure (Adjacency Matrix vs. List) 14 |
| **Graph Traversal** | traverse, both, out, in, repeat | Complexity grows with depth; requires efficient join or recursion logic 17 |
| **Rich Querying** | filter, match, group\_count, order | Offloaded to native query engines where possible (SQL/Cypher) 15 |

14

For an abstraction to remain backend-agnostic, the protocol must handle the identification of nodes and edges consistently. In many graph libraries, such as rustworkx, the add\_node method returns a unique integer index that serves as the handle for that node throughout its lifecycle.26 In more complex distributed systems like GraphScope, nodes may be identified by tuples that include labels and IDs, particularly when the graph is partitioned across multiple machines.20 The abstraction layer must normalize these various identification schemes into a single, type-safe contract that the application code can rely upon.27

## **Type Safety and Interface Contracts in Python: ABCs vs. Protocols**

Maintaining type safety and clear contracts is paramount when building an abstraction layer that supports multiple, fundamentally different backends. In the Python ecosystem, two primary mechanisms exist for defining these contracts: Abstract Base Classes (ABCs) and Protocols (PEP 544).29 The choice between these mechanisms significantly impacts the flexibility and rigidity of the architecture.

Abstract Base Classes provide nominal subtyping, where a class must explicitly inherit from the ABC to be considered a valid implementation.30 This approach is ideal for enforcing strict contracts and providing default method implementations that can be shared across all backends.3 Python's abc.abstractmethod decorator is the primary tool for this, as it prevents the instantiation of any subclass that fails to implement the required methods, ensuring that every backend implementation is complete.3

In contrast, PEP 544 introduced Protocols, which enable structural subtyping, or static duck typing.29 A class is considered to satisfy a Protocol if it implements the required methods and attributes with the correct signatures, regardless of its inheritance hierarchy.29 This is particularly advantageous when integrating third-party storage drivers or legacy code that cannot be easily modified to inherit from a new base class.30 Protocols allow for a more modular and composable design, where an object can support multiple interfaces (e.g., Readable, Writable, Traversable) simultaneously.30

| Feature | Abstract Base Class (ABC) | Protocol (PEP 544\) |
| :---- | :---- | :---- |
| **Subtyping Type** | Nominal (Explicit) | Structural (Implicit) |
| **Runtime Enforcement** | Strong; prevents instantiation of incomplete classes. | Opt-in via @runtime\_checkable decorator. |
| **Static Verification** | Supported by type checkers (mypy/pyright). | Excellent; allows for deep structural verification. |
| **Default Logic** | Can provide robust default implementations. | Default logic is ignored during implicit checks. |
| **Composition** | Traditional multiple inheritance. | Easy merging and extension of interfaces. |

29

For a graph storage layer, the architect might define a GraphStorage Protocol that specifies methods for add\_node and add\_edge. A simple in-memory implementation using Python dictionaries can satisfy this protocol without any boilerplate, while a complex Hyperledger Fabric adapter can be explicitly verified against the same protocol using static analysis tools.16 This dual capability—supporting both the simplicity of fakes and the rigor of production backends—makes Protocols a highly effective tool for modern storage abstractions.30

## **Relational Persistence: Implementing the PostgreSQL Backend**

When PostgreSQL is selected as a backend for a graph storage layer, the abstraction must bridge the gap between the relational model and the graph model. This is typically achieved using an ORM such as SQLAlchemy, which provides a sophisticated toolkit for mapping Python objects to relational tables.15 SQLAlchemy’s architecture is centered on the Engine, which manages database connections and uses a Dialect to translate generic SQL expressions into the specific syntax required by PostgreSQL.15

In a relational graph implementation, vertices and edges are usually stored in separate tables. The nodes table might contain columns for the ID, label, and a JSONB column for properties, while the edges table stores the source ID, destination ID, and edge attributes.16 To implement the traverse method, the abstraction layer must often resort to recursive Common Table Expressions (CTEs) or multiple join operations, which can be computationally expensive.6 The role of the PostgreSQL adapter is to encapsulate these SQL complexities, providing the appearance of a native graph interface to the application code.15

| Relational Construct | Graph Equivalent | Implementation Strategy |
| :---- | :---- | :---- |
| **Table** | Vertex or Edge Collection | One table per node label or a unified nodes/edges schema. |
| **Row** | Individual Node or Edge | Mapped to a domain entity via an ORM mapper. |
| **Foreign Key** | Relationship (Edge) | Links the edges table to the nodes table for referential integrity. |
| **JSONB Column** | Properties/Metadata | Stores arbitrary key-value pairs for flexible schema support. |
| **Recursive CTE** | Traversal/Path Query | Enables depth-first or breadth-first search within SQL. |

3

A critical aspect of the PostgreSQL backend is the management of transactional consistency. The repository implementation should generally keep the .commit() operation outside of its internal methods, leaving the responsibility of transaction finalization to the caller or a higher-level Unit of Work pattern.3 This allows multiple repository operations—such as adding a node and its associated edges—to be wrapped in a single atomic transaction, mitigating the risk of data corruption.3

## **Ephemeral and High-Performance Persistence: The In-Memory Backend**

In-memory storage backends are essential for scenarios requiring extreme low latency, such as real-time graph algorithms, or for isolating logic during unit testing.1 These implementations typically forgo the overhead of networking and disk I/O, instead utilizing Python’s efficient built-in data structures.18 A common pattern for in-memory graph storage is the adjacency list, implemented as a dictionary of dictionaries where the outer keys are node IDs and the inner keys are the neighboring nodes.14

NetworkX, a prominent Python graph library, provides a quintessential example of this architecture. Its graph objects are essentially wrappers around these nested dictionaries, providing methods for reporting nodes, edges, and neighbors.18 Because the data is stored in memory, traversals are remarkably fast, involving simple dictionary lookups rather than complex SQL joins or network round-trips.18 However, the ephemeral nature of in-memory storage means that any data is lost upon process termination, making it unsuitable for durable long-term storage unless combined with a persistence mechanism like pickle or marshal.39

| Storage Mechanism | Performance Characteristic | Best For |
| :---- | :---- | :---- |
| **Adjacency List (Dicts)** | **![][image1]** for neighbor lookup; ![][image2] for iteration. | Dense traversals and local algorithms. 18 |
| **Adjacency Matrix (NumPy)** | **![][image1]** for edge check; ![][image3] for neighbor iteration. | Mathematical graph analysis and large-scale operations. 14 |
| **In-Memory Cache (Redis)** | Higher latency than local RAM; allows shared state. | Multi-instance applications requiring shared graph views. 16 |
| **Serialized (Pickle/JSON)** | Slowest; provides basic persistence for in-memory stores. | Small datasets and configuration storage. 39 |

14

The in-memory adapter within the storage abstraction layer serves as a high-fidelity "fake" that can be swapped in for the PostgreSQL backend during development or testing.1 By adhering to the same structural protocol and type-safe contracts, the in-memory backend ensures that the application's graph logic is thoroughly verified before it is ever deployed against a production database.28

## **Distributed Ledgers and Immutable Graphs: The Hyperledger Fabric Backend**

Integrating a blockchain backend like Hyperledger Fabric into a graph storage abstraction introduces a paradigm shift in how data integrity and consistency are managed. Unlike traditional databases, Fabric is a modular, distributed ledger platform designed for enterprise environments where confidentiality and traceability are paramount.4 In this architecture, the "ledger" is split into two components: a "World State" database that stores the current value of assets as key-value pairs, and an immutable "Transaction Log" that records the history of all changes.4

For a graph storage layer, nodes and edges are treated as assets within the Fabric network. "Adding a node" involves initiating a chaincode transaction that updates the World State.4 This process is fundamentally different from a relational write; it requires a transaction proposal to be endorsed by a set of peer nodes, ordered by a consensus service (such as Raft or PBFT), and finally committed to the ledger.4 The abstraction layer must encapsulate this complex lifecycle, providing a standard add\_node method that internally manages the asynchronous communication with the Fabric network.24

| Fabric Component | Graph Abstraction Mapping | Technical Mechanism |
| :---- | :---- | :---- |
| **World State** | Current Graph Structure | Stores nodes and edges as JSON/Binary key-value pairs. 4 |
| **Transaction Log** | Graph Evolution History | Records every addition or deletion for provenance tracking. 4 |
| **Chaincode** | Storage Protocol Logic | Smart contracts that enforce graph invariants (e.g., no orphaned edges). 4 |
| **Channels** | Private Graph Partitions | Restricts graph access to a specific subset of network participants. 4 |
| **Endorsement** | Write Permission/Validation | Ensures that graph modifications are verified by trusted peers. 4 |

4

One of the primary advantages of a Fabric backend is its ability to support rich queries if CouchDB is used as the World State database.23 This allows the abstraction layer to execute complex lookups against node and edge attributes using a selector syntax similar to MongoDB.23 However, the distributed nature of the blockchain and the overhead of consensus introduce significant latency, making the support for asynchronous operations within the abstraction layer a critical requirement for production readiness.4

## **Synchronous and Asynchronous Interoperability: Patterns for Dual Interfaces**

Modern Python applications increasingly demand support for both synchronous and asynchronous I/O, particularly when interacting with high-latency storage like cloud object stores or blockchain networks.34 This requirement creates a "function coloring" problem, where synchronous and asynchronous code cannot be easily mixed without blocking the event loop or introducing complex threading models.10

Architects of storage abstraction layers employ several distinct strategies to handle this dual requirement:

1. **Code Duplication:** Some libraries, such as the Azure SDK, provide entirely separate sync and async clients (e.g., azure.storage.blob and azure.storage.blob.aio).42 While this offers the best performance and type safety for each model, it results in significant code duplication and the risk of logic drift between the two versions.10  
2. **The "fsspec" IO Thread Pattern:** Libraries like fsspec and zarr maintain an async-only core implementation and provide a synchronous wrapper for traditional code.42 The library starts a dedicated background thread running an asyncio event loop; synchronous calls are submitted to this loop as coroutines and the calling thread blocks until the result is returned.42 This approach is favored for its ability to provide concurrent performance to synchronous users, though it is considered fragile due to potential deadlocks and threading complexities.42  
3. **The "Sans-IO" Pattern:** This pattern involves implementing the core protocol logic (e.g., graph traversal algorithms, data serialization) as purely synchronous functions that operate on bytes or in-memory buffers.9 By removing all I/O from the core, the logic can be reused in both synchronous and asynchronous contexts without duplication.9 The I/O-specific code (e.g., socket manipulation, HTTP requests) is pushed to the very edges of the system, where it is implemented natively for each environment.9

| Strategy | Performance | Maintenance | Best For |
| :---- | :---- | :---- | :---- |
| **Duplication** | High; native for both. | High; risky logic drift. | High-traffic drivers where every microsecond counts. 10 |
| **fsspec Threading** | High; allows concurrency for sync users. | Medium; complex threading edge cases. | Data science libraries (fsspec, zarr, dask). 42 |
| **Sans-IO** | Moderate; requires wrapping. | Low; logic is unified. | Protocol parsers and complex traversal engines. 9 |
| **Blocking Wrapper** | Low; no concurrency benefits. | Very Low; simple dispatch. | Simple CRUD apps where async is a niche requirement. 10 |

9

For a graph storage abstraction, the "Sans-IO" approach is particularly suitable for the traversal engine, which can be implemented as a state machine that requests data from a generic "provider".9 The provider implementation then fulfills these requests either synchronously (for the in-memory backend) or asynchronously (for the Fabric backend), ensuring that the complex graph logic remains consistent across all environments.9

## **Backend Swapping and Dependency Injection: Configuration-Driven Architecture**

A central requirement of the storage abstraction layer is the ability to swap backends seamlessly via configuration or dependency injection.1 This capability allows application code to be developed against an in-memory store and deployed against a production PostgreSQL or Fabric instance without modifying the core business logic.3

The NetworkX "plugin-dispatch" architecture provides a robust model for this.47 In this system, backends are registered as entry points in the Python package metadata.27 At runtime, the library looks for environment variables (e.g., NETWORKX\_BACKEND\_PRIORITY) or specific keyword arguments to determine which backend should handle a given operation.27 If a backend only partially implements the protocol, it can provide a can\_run function that inspects the query arguments and returns whether it is capable of executing the request.27

Dependency injection frameworks can further simplify this by managing the lifecycle of repository instances. A UserService might depend on a UserRepository Protocol; at startup, the DI container injects either a SqlAlchemyUserRepository or an InMemoryUserRepository based on the application's configuration.30 This approach ensures that the service layer remains decoupled from the specific storage technology, adhering to the principle of programming to an interface rather than an implementation.48

| Injection Mechanism | Swap Method | Key Benefit |
| :---- | :---- | :---- |
| **Entry Points** | Metadata registration at install time. | Zero-code changes for backend activation. 47 |
| **Factory Pattern** | GraphFactory.open(config) | Centralized control over backend instantiation. 50 |
| **Dependency Injection** | Constructor injection of repository Protocol. | Cleanest separation for testing and service layers. 30 |
| **Env Variables** | NETWORKX\_BACKEND\_PRIORITY=postgres | Easy configuration for CI/CD and multi-tenant environments. 28 |

28

By combining these patterns, architects can build systems that are not only flexible but also highly adaptable to future requirements. If a new blockchain backend is introduced, it simply needs to implement the established graph protocol and register itself as a valid provider, allowing existing applications to leverage the new technology with minimal friction.27

## **Evolving the Abstraction: Backward Compatibility and Stability**

As the storage abstraction layer matures, the ability to evolve the interface without breaking existing backends becomes a critical maintenance concern.51 Changes to the protocol must be managed carefully, particularly in a multi-backend environment where third-party developers may have implemented custom adapters.47

Best practices for interface evolution include the adoption of semantic versioning and clearly defined deprecation policies.51 When a breaking change is necessary, the "Expand, Migrate, Contract" pattern provides a safe path forward. The developer first introduces the new API alongside the old one (Expand), allows time for backend implementations to update (Migrate), and finally removes the legacy interface in a subsequent major release (Contract).52

| Compatibility Strategy | Description | Impact on Storage Layer |
| :---- | :---- | :---- |
| **Additive Changes** | Adding new methods/columns without altering existing ones. | safest for maintaining legacy backend support. 52 |
| **Dual-Write Pattern** | Writing to both old and new schemas during a migration. | ensures data consistency during major refactors. 52 |
| **Semantic Versioning** | Using MAJOR.MINOR.PATCH to signal change impact. | provides clear expectations for backend maintainers. 51 |
| **Grace Periods** | Maintaining support for old interfaces for a set time (e.g., 1 year). | critical for enterprise and open-source stability. 13 |

13

Furthermore, maintaining a persistence-ignorant interface is key to long-term stability.13 Repository interfaces should avoid exposing technology-specific features, such as SQLAlchemy's IQueryable or Fabric-specific transaction IDs, instead returning standard Python collections or domain entities.13 This ensures that the contract between the domain and storage remains focused on "what" needs to be stored rather than "how" it is implemented, allowing both sides of the abstraction to evolve independently.6

## **Verification and Conformance: Shared Test Suites and Property-Based Testing**

The final pillar of a robust storage abstraction is a rigorous verification framework that ensures all backend implementations adhere to the defined protocol. This is best achieved through the "Shared Test Suite" pattern, where a single set of standardized tests is executed against every adapter.28 Pytest’s parameterization feature is the ideal tool for this, allowing a developer to define the test logic once and run it with multiple repository instances.54

Property-based testing, implemented via the Hypothesis library, takes this verification to a deeper level.56 Instead of testing only against specific inputs, Hypothesis generates a wide range of arbitrary data and asserts that certain invariants always hold true.56 For a graph layer, this might include verifying that the number of nodes reported by the graph always matches the number of successful add\_node calls, or that a traversal across a randomly generated graph produces the same results regardless of the backend implementation.28

| Testing Level | Primary Objective | Key Technique |
| :---- | :---- | :---- |
| **Unit Testing** | Verify internal logic of the adapter. | Pytest with in-memory mocks. 3 |
| **Integration Testing** | Verify interaction with the real backend. | Pytest-django or SQLAlchemy engines with real DBs. 37 |
| **Conformance Testing** | Ensure backend-agnostic behavior. | Shared Pytest suite parameterized with all backends. 28 |
| **Property-Based** | Discover edge cases and race conditions. | Hypothesis strategies for graph generation. 56 |
| **Compatibility Testing** | Verify behavior across Python versions. | Running tests in parallel with tox or virtualenv. 58 |

3

NetworkX facilitates this by allowing backends to register a special on\_start\_tests function, which can inspect the discovered tests and mark those that the backend does not yet support as "expected to fail" (xfail).27 This allows the core library to maintain a single source of truth for its test suite while providing backends with the flexibility to evolve at their own pace.28 Through these comprehensive testing strategies, architects can provide a high level of confidence that the storage abstraction layer is both correct and reliable across its entire multi-backend landscape.37

## **Conclusions on Multi-Backend Storage Abstraction**

The design of a graph storage abstraction layer is a multifaceted architectural endeavor that requires the careful integration of structural and behavioral design patterns. By centering the architecture on a well-defined protocol—leveraging the flexibility of Python's Protocols and the rigor of ABCs—designers can create a system that is both type-safe and highly extensible. The transition from high-level domain intents to backend-specific implementations, such as PostgreSQL's relational tables or Hyperledger Fabric's distributed world state, is managed through the Repository and Adapter patterns, ensuring that the core business logic remains isolated from infrastructural volatility.

Supporting both synchronous and asynchronous operations necessitates a sophisticated approach to I/O management, with the "Sans-IO" and "IO Thread" patterns providing proven solutions for reconciling the "function coloring" problem. Furthermore, the ability to swap backends via configuration, supported by plugin-dispatch systems and dependency injection, empowers developers to build applications that are future-proof and resilient to technological shifts. When combined with rigorous conformance testing and a commitment to backward compatibility, these patterns form the foundation of a modern, professional-grade storage abstraction that can navigate the complexities of contemporary data persistence.

#### **Works cited**

1. notes/books/python-architecture-patterns/notes.md at master · pkardas/notes \- GitHub, accessed February 17, 2026, [https://github.com/pkardas/notes/blob/master/books/python-architecture-patterns/notes.md](https://github.com/pkardas/notes/blob/master/books/python-architecture-patterns/notes.md)  
2. Whats the diff betn Repository pattern and adapter pattern ? : r/dotnet \- Reddit, accessed February 17, 2026, [https://www.reddit.com/r/dotnet/comments/1ll8exy/whats\_the\_diff\_betn\_repository\_pattern\_and/](https://www.reddit.com/r/dotnet/comments/1ll8exy/whats_the_diff_betn_repository_pattern_and/)  
3. Repository Pattern \- Cosmic Python, accessed February 17, 2026, [https://www.cosmicpython.com/book/chapter\_02\_repository.html](https://www.cosmicpython.com/book/chapter_02_repository.html)  
4. Introduction — Hyperledger Fabric Docs main documentation, accessed February 17, 2026, [https://hyperledger-fabric.readthedocs.io/en/latest/blockchain.html](https://hyperledger-fabric.readthedocs.io/en/latest/blockchain.html)  
5. Leaky abstraction \- Wikipedia, accessed February 17, 2026, [https://en.wikipedia.org/wiki/Leaky\_abstraction](https://en.wikipedia.org/wiki/Leaky_abstraction)  
6. Leaky Abstractions \- Devopedia, accessed February 17, 2026, [https://devopedia.org/leaky-abstractions](https://devopedia.org/leaky-abstractions)  
7. Leaky Abstraction \- Khalil Stemmler, accessed February 17, 2026, [https://khalilstemmler.com/wiki/leaky-abstraction/](https://khalilstemmler.com/wiki/leaky-abstraction/)  
8. About leaky abstractions \- Mathieu Ropert, accessed February 17, 2026, [https://mropert.github.io/2017/11/08/leaky-abstractions/](https://mropert.github.io/2017/11/08/leaky-abstractions/)  
9. how-to-sans-io.rst \- GitHub, accessed February 17, 2026, [https://github.com/brettcannon/sans-io/blob/master/how-to-sans-io.rst](https://github.com/brettcannon/sans-io/blob/master/how-to-sans-io.rst)  
10. Maintaining a separate async API : r/Python \- Reddit, accessed February 17, 2026, [https://www.reddit.com/r/Python/comments/1pme2nx/maintaining\_a\_separate\_async\_api/](https://www.reddit.com/r/Python/comments/1pme2nx/maintaining_a_separate_async_api/)  
11. Design patterns that I often avoid: Repository pattern \- InfoWorld, accessed February 17, 2026, [https://www.infoworld.com/article/2248622/design-patterns-that-i-often-avoid-repository-pattern.html](https://www.infoworld.com/article/2248622/design-patterns-that-i-often-avoid-repository-pattern.html)  
12. Architecture Patterns with Python \- Tyler Hillery, accessed February 17, 2026, [https://tylerhillery.com/notes/architecture-patterns-with-python/](https://tylerhillery.com/notes/architecture-patterns-with-python/)  
13. Design Your Repository Like a Senior — and Avoid Common Anti ..., accessed February 17, 2026, [https://medium.com/clean-code-playbook/design-your-repository-like-a-senior-and-avoid-common-anti-patterns-9aacc2df3554](https://medium.com/clean-code-playbook/design-your-repository-like-a-senior-and-avoid-common-anti-patterns-9aacc2df3554)  
14. PythonGraphApi \- Python Wiki, accessed February 17, 2026, [https://wiki.python.org/moin/PythonGraphApi](https://wiki.python.org/moin/PythonGraphApi)  
15. Ultimate guide to SQLAlchemy library in python \- Deepnote, accessed February 17, 2026, [https://deepnote.com/blog/ultimate-guide-to-sqlalchemy-library-in-python](https://deepnote.com/blog/ultimate-guide-to-sqlalchemy-library-in-python)  
16. Red-Bird: Repository Patterns for Python — Repository patterns for Python, accessed February 17, 2026, [https://red-bird.readthedocs.io/](https://red-bird.readthedocs.io/)  
17. Apache TinkerPop graph computing framework | DataStax Enterprise, accessed February 17, 2026, [https://docs.datastax.com/en/dse/6.9/graph/reference/traversal/tinkerpop-framework.html](https://docs.datastax.com/en/dse/6.9/graph/reference/traversal/tinkerpop-framework.html)  
18. Introduction — NetworkX 3.6.1 documentation, accessed February 17, 2026, [https://networkx.org/documentation/stable/reference/introduction.html](https://networkx.org/documentation/stable/reference/introduction.html)  
19. Graph—Undirected graphs with self loops — NetworkX 3.6.1 documentation, accessed February 17, 2026, [https://networkx.org/documentation/stable/reference/classes/graph.html](https://networkx.org/documentation/stable/reference/classes/graph.html)  
20. Graph types \- GraphScope documentation, accessed February 17, 2026, [https://graphscope.io/docs/reference/networkx/graphs](https://graphscope.io/docs/reference/networkx/graphs)  
21. 17.3 Representing Graphs in Python, accessed February 17, 2026, [https://www.teach.cs.toronto.edu/\~csc110y/fall/notes/17-graphs/03-representing-graphs.html](https://www.teach.cs.toronto.edu/~csc110y/fall/notes/17-graphs/03-representing-graphs.html)  
22. Graph Query Language \- Gremlin \- Apache TinkerPop, accessed February 17, 2026, [https://tinkerpop.apache.org/gremlin.html](https://tinkerpop.apache.org/gremlin.html)  
23. Hyperledger Fabric Model \- Read the Docs, accessed February 17, 2026, [https://hyperledger-fabric.readthedocs.io/en/latest/fabric\_model.html](https://hyperledger-fabric.readthedocs.io/en/latest/fabric_model.html)  
24. Couchbase Integration with Hyperledger Fabric: A Technical Deep Dive, accessed February 17, 2026, [https://www.couchbase.com/blog/couchbase-integration-with-hyperledger-fabric-a-technical-deep-dive/](https://www.couchbase.com/blog/couchbase-integration-with-hyperledger-fabric-a-technical-deep-dive/)  
25. GraphRAG-RS: Production-Ready Knowledge Graph Platform with Multi-Interface Architecture | by Carlo C. | GoPenAI, accessed February 17, 2026, [https://blog.gopenai.com/graphrag-rs-production-ready-knowledge-graph-platform-with-multi-interface-architecture-a45d41fbeea6](https://blog.gopenai.com/graphrag-rs-production-ready-knowledge-graph-platform-with-multi-interface-architecture-a45d41fbeea6)  
26. Introduction to rustworkx, accessed February 17, 2026, [https://www.rustworkx.org/tutorial/introduction.html](https://www.rustworkx.org/tutorial/introduction.html)  
27. Backends — NetworkX 3.6.1 documentation, accessed February 17, 2026, [https://networkx.org/documentation/stable/reference/backends.html](https://networkx.org/documentation/stable/reference/backends.html)  
28. Graph types — NetworkX 3.0 documentation, accessed February 17, 2026, [https://networkx.org/documentation/networkx-3.0/reference/classes/index.html](https://networkx.org/documentation/networkx-3.0/reference/classes/index.html)  
29. PEP 544 – Protocols: Structural subtyping (static duck typing) | peps ..., accessed February 17, 2026, [https://peps.python.org/pep-0544/](https://peps.python.org/pep-0544/)  
30. How to Use Protocol Classes for Type Safety in Python \- OneUptime, accessed February 17, 2026, [https://oneuptime.com/blog/post/2026-02-02-python-protocol-classes-type-safety/view](https://oneuptime.com/blog/post/2026-02-02-python-protocol-classes-type-safety/view)  
31. Understanding Python's Protocols and Abstract Base Classes: A Comparative Insight, accessed February 17, 2026, [https://www.oreateai.com/blog/understanding-pythons-protocols-and-abstract-base-classes-a-comparative-insight/54e7f59060366ff42adb0679f8a72483](https://www.oreateai.com/blog/understanding-pythons-protocols-and-abstract-base-classes-a-comparative-insight/54e7f59060366ff42adb0679f8a72483)  
32. Protocols — typing documentation, accessed February 17, 2026, [https://typing.python.org/en/latest/spec/protocol.html](https://typing.python.org/en/latest/spec/protocol.html)  
33. Python Protocols: Leveraging Structural Subtyping, accessed February 17, 2026, [https://realpython.com/python-protocol/](https://realpython.com/python-protocol/)  
34. Introducing Obspec: A Python protocol for interfacing with object ..., accessed February 17, 2026, [https://developmentseed.org/obspec/latest/blog/2025/06/25/introducing-obspec-a-python-protocol-for-interfacing-with-object-storage/](https://developmentseed.org/obspec/latest/blog/2025/06/25/introducing-obspec-a-python-protocol-for-interfacing-with-object-storage/)  
35. Engine Configuration — SQLAlchemy 2.1 Documentation, accessed February 17, 2026, [http://docs.sqlalchemy.org/en/latest/core/engines.html](http://docs.sqlalchemy.org/en/latest/core/engines.html)  
36. Features of fsspec, accessed February 17, 2026, [https://filesystem-spec.readthedocs.io/en/latest/features.html](https://filesystem-spec.readthedocs.io/en/latest/features.html)  
37. How To Test Database Transactions With Pytest And SQLModel, accessed February 17, 2026, [https://pytest-with-eric.com/database-testing/pytest-sql-database-testing/](https://pytest-with-eric.com/database-testing/pytest-sql-database-testing/)  
38. Graph types — NetworkX 3.6.1 documentation, accessed February 17, 2026, [https://networkx.org/documentation/stable/reference/classes/index.html](https://networkx.org/documentation/stable/reference/classes/index.html)  
39. Serialize Your Data With Python, accessed February 17, 2026, [https://realpython.com/python-serialize-data/](https://realpython.com/python-serialize-data/)  
40. Hyperledger Fabric \- LF Decentralized Trust, accessed February 17, 2026, [https://www.lfdecentralizedtrust.org/projects/fabric](https://www.lfdecentralizedtrust.org/projects/fabric)  
41. Hyperledger Fabric in Blockchain \- GeeksforGeeks, accessed February 17, 2026, [https://www.geeksforgeeks.org/computer-networks/hyperledger-fabric-in-blockchain/](https://www.geeksforgeeks.org/computer-networks/hyperledger-fabric-in-blockchain/)  
42. Async and sync interfaces \- Pangeo Discourse, accessed February 17, 2026, [https://discourse.pangeo.io/t/async-and-sync-interfaces/5190](https://discourse.pangeo.io/t/async-and-sync-interfaces/5190)  
43. 3.0 Migration Guide \- zarr-python, accessed February 17, 2026, [https://zarr.readthedocs.io/en/stable/user-guide/v3\_migration/](https://zarr.readthedocs.io/en/stable/user-guide/v3_migration/)  
44. The case for sans-io \- fasterthanli.me, accessed February 17, 2026, [https://fasterthanli.me/articles/the-case-for-sans-io](https://fasterthanli.me/articles/the-case-for-sans-io)  
45. Async — fsspec 2025.12.0.post4+g51411a04a.d20251217 documentation, accessed February 17, 2026, [https://filesystem-spec.readthedocs.io/en/latest/async.html](https://filesystem-spec.readthedocs.io/en/latest/async.html)  
46. Network protocols, sans I/O — Sans I/O 1.0.0 documentation, accessed February 17, 2026, [https://sans-io.readthedocs.io/](https://sans-io.readthedocs.io/)  
47. Backends and Configs — NetworkX 3.3 documentation, accessed February 17, 2026, [https://networkx.org/documentation/networkx-3.3/reference/backends.html](https://networkx.org/documentation/networkx-3.3/reference/backends.html)  
48. The Repository Pattern in Python: Write Flexible, Testable Code (With FastAPI Examples) | by Muhsin Kılıç | Medium, accessed February 17, 2026, [https://medium.com/@kmuhsinn/the-repository-pattern-in-python-write-flexible-testable-code-with-fastapi-examples-aa0105e40776](https://medium.com/@kmuhsinn/the-repository-pattern-in-python-write-flexible-testable-code-with-fastapi-examples-aa0105e40776)  
49. Strategy for keeping up with (Python) language changes, accessed February 17, 2026, [https://softwareengineering.stackexchange.com/questions/187221/strategy-for-keeping-up-with-python-language-changes](https://softwareengineering.stackexchange.com/questions/187221/strategy-for-keeping-up-with-python-language-changes)  
50. Provider Documentation \- Apache TinkerPop, accessed February 17, 2026, [https://tinkerpop.apache.org/docs/current/dev/provider/](https://tinkerpop.apache.org/docs/current/dev/provider/)  
51. Investigating the Evolution of Resilient Microservice Architectures: A Compatibility-Driven Version Orchestration Approach \- MDPI, accessed February 17, 2026, [https://www.mdpi.com/2673-6470/5/3/27](https://www.mdpi.com/2673-6470/5/3/27)  
52. Database Design Patterns for Ensuring Backward Compatibility \- TiDB, accessed February 17, 2026, [https://www.pingcap.com/article/database-design-patterns-for-ensuring-backward-compatibility/](https://www.pingcap.com/article/database-design-patterns-for-ensuring-backward-compatibility/)  
53. Using different database with pytest \- python \- Stack Overflow, accessed February 17, 2026, [https://stackoverflow.com/questions/14645348/using-different-database-with-pytest](https://stackoverflow.com/questions/14645348/using-different-database-with-pytest)  
54. Learn Test Parametrization in Pytest: Running Tests with Multiple Inputs \- Codefinity, accessed February 17, 2026, [https://codefinity.com/courses/v2/1cf91e45-bf65-468b-8c09-6bc41c46bbe3/b6e40c5a-2790-4b75-89e6-bad02fbeb123/ccc30abe-66ca-466a-a74c-d3c985c787f6](https://codefinity.com/courses/v2/1cf91e45-bf65-468b-8c09-6bc41c46bbe3/b6e40c5a-2790-4b75-89e6-bad02fbeb123/ccc30abe-66ca-466a-a74c-d3c985c787f6)  
55. How to Use pytest Parametrize \- OneUptime, accessed February 17, 2026, [https://oneuptime.com/blog/post/2026-02-02-pytest-parametrize-guide/view](https://oneuptime.com/blog/post/2026-02-02-pytest-parametrize-guide/view)  
56. Hypothesis Documentation, accessed February 17, 2026, [https://hypothesis.readthedocs.io/\_/downloads/en/hypothesis-python-4.57.1/pdf/](https://hypothesis.readthedocs.io/_/downloads/en/hypothesis-python-4.57.1/pdf/)  
57. Third-party extensions \- Hypothesis 6.151.5 documentation, accessed February 17, 2026, [https://hypothesis.readthedocs.io/en/latest/extensions.html](https://hypothesis.readthedocs.io/en/latest/extensions.html)  
58. Python 3 Migration Playbook: Best Practices for Enterprises \- Clarion Technologies, accessed February 17, 2026, [https://www.clariontech.com/blog/python-3-migration-playbook](https://www.clariontech.com/blog/python-3-migration-playbook)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACMAAAAWCAYAAABKbiVHAAACpUlEQVR4AdyVyatOYRzHr3ksQ6YsZKHEQkk2JCmRMeEPEMmQUFJXComNhaREkY3S3bjJEBKlkEwLyrSQhVLXTELGz+d2ntc5T+c953jvXcjb93N+v+f3POe8v/MMv9O16R/6/ffJDGay+0JV9WTgUGgqm5neDJoO82EklMkxJxjUA6qqGwNbYFy9ZMbSeQrOgMlMxl6GCzAc8tSLoA/djH0PsboT2ADxrH0mtgZa4mS6ENwCV+AwzISdsB0mQh+4Af0h1m4C9+E2BDlDa2nshaewD/pBrCcEWuNkvGkbHQvhNKTlG5joaIKbIK0BNFbCfkjL57vU5whegyIddHAYsAhnI+yCm5An3/oXHQsgrWU0HidgavqK5wtexH6AIrWFZAYy6gC8A6cSk6sfRE1mDDatpTSuQ4cUklnOUzwJx7GfoJ5G0eE9JoXbLk+D+8lZaw80evHB3jvXC5yHIk1NOh8mVuNLuCnbbHQEk7HoTEseciux9UzYK+nN7RI7/q2XCnhic4eZjJ3WgJ+MeAn1NIwOT5k15Ah+kC+j/8VLBfy/3GEm445/Rq++dQE3V9YaC5tF7XVqxJvE93gnbqEpTMY7r3qBSZCneQRXwyGwGGJqepV4gxJbZkqTaeYJrrlv7+mgWdMSPMv8Huw6iPWRwHOIjzuhjMJyOruZjtBwafRfcJkNI8B6sR5rlb2EXQVzwOqbPtKEanLclFor69yjaUFcjLXw+Tl5gG85wfxRSMaIJ8ll8lviLD0iuAJmQVhG3FydJeqJ9CDgZjSBlh9e95T4wuOJHYWM0snY8Y3LHTgG/oEbG7dUrYxwU7ukuA1pRpxMQ0/hJpfPfedJi/cc3aVyUzd3VjL+m4XwJM4O+Fu5R+92ZjIm4Bf/O84QqCoruPto628AAAD//zR0QywAAAAGSURBVAMAIWFqWWpcaF8AAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEsAAAAWCAYAAACIXmHDAAAFgklEQVR4AeyYd6gdRRSHx95774KKihobGnsBe6yofyiIvUTEKHaxYUFNsGMXFA32XrCLsVcQFUtIQhrpvffk+5ady9x9+94ueS+BG3I5vz1nztQ9c+ac2btiWP6rbYHlxqptqhCWhLE2ZP41wTJHVcZanTc+HJwItgRVZJu3aLQKqCLn3ohGK4OWIBdcttCdUb4PPgQaaz/4V+BTsBkoo9VQvgquA5NBR/QnlXPBOLAjaAkqGmsFVn0T6AeeBUeBO8HtYG+wBvgJrA2KdA+Kv8BvoIq60cCNGAv/H7QEFY31IKu+DZwMPgApzaSgIbeHXwNSWo/CxeBRUJf2peE3YCFoCUqNdSorvgrcDX4BZaTX+HInFSrPo6yHCMRK2okWWwE9GNYaFI21Pst9HEwCD4P2aD4VGqsYZ85A/wPoiIx1p9DAvkfApTJjuZYTqDwAtBf816WuB9A7YU20C6VDgX0NKwcidwfKsCaqM1dc917RWBcwhJnsZfh00B5tS4V9NBpiRivxNJ7pdYhtyPb3o30DbA1eBFeD8eBvEGljhOeBSWQ3+OnAJFN8ybPRGzc1uuO8R3kYMAPvCe8D7gAfgVeAmfwuuCEGllGduQw3zq9NlHv5IvZ2J+Wf+OgAB+d1/+ZcppHXQhgDyuhplB5T46Deez7lXcG3YAGQNuDxNXAXD4H7wmbVPZDTZGJc1KCnoX8EnANs4+aZXW+g3Au4ccfA3wG+7NFw73+wUGeu7Wj4PRgFTHLO1VNjrYpCt4WFX310gBir0uCvK9tloo8CDqN8ETAOesQRwzwfQOPAMrJeb9JTfGk9UMO+Se1UIG3D4wHgy6ex0Y36Dr3khg1C8Nj9A38NDAG3ArM6LNSZ6wka+l4aHzHswKOvxtLNPd/usqkcfSltilbv8A71HHIkja08y0cB1+flj3MuK8Yrj/G5VEwBGsNjZUaWazzUGRkq1kF6G0TSQ12XWVWdCcr73v4UPgfSNB4aaCC8zlxb0O544CYZMt5Fdh19NNZsCoOBsucesZS8a7kQj4fxJjaakAteH3KxwQzAwykNAJG85OqFXkzV+bJ6h8YxvpgELqHiM5CSY7mh/UJoqI/MpTRRaCjvg6nn5s1CnbmMTzrQM3TyJLmeK5B/1kDwEN3YBVkuwsxzGcqngJdVWIO8hVswFshT+I3o2U91epae4Isbf/RUM+zItFEubw6Pa5yDbBs9EDEjY9EIpPRYuhmO7RxUNVGdudxIOzmXvIG4kBvR2Ejv0VUpNsis5GdMbzRaGNZEuqveY3ZqqqDwI9gERPI4GHsMwH5COecMKr8AegSsQda/Til6rEfZBGAsQR2u5eGuFz3IOOmXRPR4mjWozlyegv/oUVzPcdFYWvFYGriT3peuRPaW/iX8UuAZ9vZu1qHYhmx3UBttCI5jDDBYm8pH00ZvcgM0nFkPVfDYmfX6UrgPGNhtY5bWoKjCCyEE74B6qkfUtQZ+RWP5KZUmIJo0UdVcJqCz6NEdeJJco3GrWzQW+iwTegwvp+ACte6FyKbgeEwplpKGMKOaKNIG/SmY5R6Cu4DH4AZqY4HGcJNQBWOmnnRzCOFJcCbQ2w3OiBm5UcZLx3NN9rHCD3x5hB4RM1/Updx+VXP9QYfdgYbyfubXTe/UWNQF0/bvCC8BDeDAiJVkhjLoa4BiY+ORrp3GGo9taojYZyiCqd4+iA3aB8lFm2AQM3IuL7VmuUyRPxzD98iL7TLblc0VOxj3HDtuaJf9+eeu6wnufDHmxck7w++lsxdS/19z/Fsoa8Ce8KVGRc/qzMTGCc+2nxqdGaesr/cvb/xeSI2PJg0/sarCQ9lYi63rSmO5CIO2AdJvL8tdBQO6wb4HA3r18JPGmzrFpUeLAAAA//8+WlJ7AAAABklEQVQDAEHXJc/+JHhFAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAWCAYAAACyjt6wAAADA0lEQVR4AeSWWahNURjHjddYLgkpY4ryJHkhvIiMEeKNSGSOFF0hoXgwlRCelJRIF2WIEkmGkAdDHozpmiUh4+9Xe5322WedfR7ufVD39v/t71vfWnufb6/h27dZk//8r1Em2IlFaQv1VXseUF1pBlszaCRMgO5QSY45zqCWUF/5krXlEuzP02vhNJjgEOwlOAddIaZWBI/CKvgMqobLU3gCj0G7C5vWdBqv4Bk49jxWveFSk02wKcE1cBkOwCjYCOthELSB6+D0Y4q0mdZ9uAVBxgbQcGb7Yn3GMmxax2hsg48wBcZA0JVsgtvpWQeT4BSk9Y2GyffGroS0OtCYB7shq+8EnJ3mWF8QUyTjM4nMgDvwFwpKJziZ6HLYBDcgJmfHB0zMdM6m/SgBU6LnSaRnYtNmEY0L4P2YYoUEqwnvgU+wE8rpNx0m2A+b1jQa16CcnEH7sgm69LPo2AJRhQTn0OvgI9ivUE7+gPeYaBjjErm3nN0Qy9oXSaBHYoPZgeO2cRvglsofMzrOC5yFPA1LOh8kVuOLtcPx1GGiii3xWEb+gXBqcUtlglWEh4O66SWHsPfSB8jt4S2eQm2M7Ax6WDzhK2KD0zETtLS0IOjbvMWWUxc6PN3WuIP4Qb6gftllojM7g2uJHYLXkCsT/MEIC6R+3hfAWmgxthC/556gD4ljqUncEuMMerh60TMQRsBeqCiTctBVLzAYYhpPcAHsAws4pqB3idcxsTHjJNTR4VdoP3YJuGKYfIUEVzPMPeQseSppFjQVz0+Y1X4xflZfCLyEbOkhVCRLjdvJL9Hdop6cRkjQveAnphtjrWdLsX4tLmLngyfOcpAuL4QLctzQQivuuI3ESYiPiERDgnZ5gl3ihTSczYfYuTAawhbAjeoMUSuBhw03Kj8Afq3y6mzJjekE7fzJ5TYcBn/UN8atqBOM8OC4HXCjcmnvRXtygtkEc4bmdrn07mNPeHYP595YobOqoRL0dyzeJ3E2QENpa0MmaFL+J/QLpzPUV314QN0/AAAA///Im42GAAAABklEQVQDAHdUiFnK0o40AAAAAElFTkSuQmCC>