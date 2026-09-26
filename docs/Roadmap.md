Rule: one phase at a time. Stop at "Done when" and write docs/progress/phase-XX.md.


[x] Phase 0
### Goal: Project skeleton
- A python fastAPI app in backend folder - with virtual env, config.py, requirements.txt
- Add docker file to setup elastic search in docker container
- A react app with router in frontend folder - with eslint, tsconfig, api/client.ts files.
- An frontend api client in api/client.ts to invoke the apis in the backend folder.

### Done When:
- FastAPI app runs on port 8000 with .venv folder(virtual env), .env.example, config.py
- Frontend runs on port 3000 with decent landing page.
- Frontend can connect to apis in backend.


[x] Pahse 1
### Goal: Add a data store layer
- Add a elastic search file that connects to elastic search running in local docker container.
- In the ElasticSearch file, add a class called `Elastic Search Store` that has methods to create index, index data and search data from elastic search.
- Refer architecture.md for data model.

### Done When:
- A data store layer is created which handles elastic search indexing and retrieval
- A index is added in elastic search.


[x] Phase 2
### Goal: Add an embedding layer
- Add a embedding file which process the data passed to it and return the vector embedding.
- This embedding file should use SentenceTransformer to load model mentioned in .env file and use it to embed.
- Add a embed method inside a `Embedding Provider` class that has logic to embed the text passes to it.

### Done When:
- An embedding layer is added which handles embedding.


[x] Phase 3
### Goal: Add a chunking layer
- Add a pre-chunking function that does data cleaning(removes the null/nan data).
- Fetch the data from the hugging face dataset mentioned in .env and store it in elastic search.
- The data is already in row format, so make each row as a chunk.
- Use the embedding provider added in phase2 to embed the chunk.
- Refer to architecture.md for inserting data.

### Done When:
- A chunking layer is added which cleans data, chunk, embed it and then insert data to elastic search.
 

[x] Phase 4
### Goal: Add a retrieval layer
- Add a retrieval layer, which can retrieve data using BM25, semantic search(Cosine similarity), Hybrid search with weights, Hybrid search with RRF.
- All retrival mechanisms should use elastic search only.
- In retrieval layer, add a class `Retrieval Registry` which has method for each retrieval mechanism.

### Done When:
- A retrival layer is added which can do different types of retrieval using elastic search.


[x] Phase 5
### Goal: Add apis to setup for retrieval
- Add an api `/get_chunks` which fetches first 10 chunks from elastic search.
- Add an api `/retrieve` which is for retrieval. This should be a POST request with payload containing search type, weight if weighted average hybrid.

### Done When:
- All the three apis are ready and working well.


[x] Phase 6
### Goal: Add UI
- Refer docs/UIDesign.md and add a clean and interactive UI.
- If any of the apis are not added, just do the UI, api can be integrated in next phases.

### Done When:
- A UI is generated with navbar and pages as mentioned in the UIDesign.md.
- Frontend is able to connect to backend through apis mentioned in UI Design.md


[x] Phase 7
### Goal: Integrate LLM
- Setup a local ollama model for reasoning in docker container to generated responses.
- Add a LLM query layer, where on user query, first retrieval happens then LLM generates a natuaral language response and also returns citations.
- The LLM response type should be JSON - {'response': <Natural language response>, 'citations': <List of citations>}
- Add an `/query` api to connect this functionality in frontend `ask` page.
- This api should have payload for sending the retrieval mechanism and user query. 

### Done When:
- An LLM query layer is added which handles data retrieval and then the natural language response generation.
- A `/query` api is added in backend that connect the LLM query layer.
- Frontend `ask` page should be able to invoke the query api and show the response with citations in the side panel.


[x] Phase8
### Goal: Run Evaluation
- Add a Evaluation layer to evaluate responses(for all retrieval mechanisms) from test Q&A dataset from huggingface.
- Take 100 questions from 4.72k. Choose questions randomly, do not take straight 100 questions.
- Use RAGAS to evaluate responses, ** Suggest if you find any better evaluation metrics for RAG sytem like this **
- Add latency and error rate also to evaluation metrics.
- Store Huggingface QA id also in the evaluation data that points to source.
- Use Lanfuse for evaluation, if any setup is needed, give me langfuse-setup guide.
- Add an `/evaluate` api to trigger evaluation. This api should have payload for sending the retrieval mechanisms and test data, state - **Progress / Done / Stopped**
- Add `/get_evals` api which loads the evaluations done with evaluation metrics, test dataset length, date and time, retrieval mechanisms.
- Check Evaluate page from `docs/UIDesing.md` and finish the pending UI part to trigger and show evaluations. 

### Done When:
- An evaluation code is setup to test data of size 100.
- An `/evaluate` api is ready to invoke for test corpus and specified retrieval mechanism.
- An UI evaluate page is ready to trigger and see and analyse the evaluations.


[x] Phase9
### Goal: Run evaluation on querying in `ask` page
- Update the `/query` api to accept `evaluation` value which should be a boolean. If the value is true, you need to run the evaluation for that query alone.
- Update `ask` page UI as per `Evaluation toggle in Ask Page` section in `docs/UIDesign.md`

### Done When:
- The `ask` page UI should have design to select retrieval strategy and evaluation checkbox with updated payload for `/query` api invocation.
- The `/query` api should retrieves data, pass it to llm for response, evalaute it and return LLM response, retrieved citations and evaluation result.



[ ] Phase10
### Goal: Query expansion
- Add the query expansion layer.
- Run the evals for 10 QA dataset without and without query expansion with the hybrid(RRF) retrieval.
- Add a query expansion toggle in `ask` page and also in `evals` page to new trigger evaluation.
- Connect this query expansion logic to `/query`, `/evaluate` api.

### Done When:
- Query expansion layer is added which does query expansion.
- Evaluation is done for 10 QA test dataset to check if query expansion improves the responses.
- UI in ask and evals pages updated with query expansion toggle.