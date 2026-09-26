## Design rules
1. Add reusable common components like loader, dropdown, button, ...
2. DO NOT write inline CSS, add css in corresponding css files.
3. Add a navbar with navigation to chunk, retrieve, ask, evals pages.
4. The UI should also handle keyboard events.


## Pages
### Chunk Page
- The chunk page should show a button `Show chunks` which invokes `/get_chunks` api and displays data in the same screen.

### Retrieve Page
- The retrieve page should have a dropdown on the top to select retrieval startegy - Lexical(BM25), Semantic, Hybrid(RRF), Hybrid(Weighted)
- If Hybrid(Weighted) is selected, show inputs to add weightage.
- Below the retrieval strategy selection, add a broad search box for querying and the retrieve button which invokes `/retrieve` api.
- The response has to be shown below the search box in tabular format showing text, chunk_index, score

### Ask
- On the top of the page, keep headings 'Ask your query'
- The sub heading should show the LLM using to generate response, get the LLM name from .env.
- This page should have a search box below the heading with submit button.
- Thge reponse from LLM should be displayed below the search box with citations as the left side collapsible panel inside the response block.
- The query submission should invoke `/query` api.

### Evaluate Page
- This page is to trigger and show the evaluations done on test Q&A already existing.
- This page should fetch evaluations data using `/get_evals` api and show them in understanding way to user. You can add tables, graphs/charts. Keep it visually clean and understanding.
- Add a evaluate button on top-right corner, on clicking it, show a popup to configure details(test data size, retrieval mechanisms) and `Start evaluation` button.
- Start evaluation button shouls invoke `evaluate` api with payload set above.
- The whole point of this page is, to identify the best retrieval mechanism for the dataset, So keep UI that compares the different retreival techniques on that evaluation.
- Also pick out the questions that actualluy affecting the metrics most.


### Evaluation toggle in Ask page
- Add a dropdown to select the retreival mechanism, if `Hybrid(Weighted)` is selected, show UI to select the weightage.
- Add a evaluation checkbox.
- These configuration options should display about the query input section. This section shoulb be expanded to full page width, with gradient background that suits with the app colors.
- Hit the `/query` api with selected retreival mechanism and evaluation value as boolean.
- `/query` api, now also returns evlauations along with response, show the evaluation and citation details in a collapsible sections below the response.



### Query Expansion
