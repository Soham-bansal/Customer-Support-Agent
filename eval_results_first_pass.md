# Evaluation results: error recovery (1 to 5)

| # | Scenario | Error seen | Approval pauses | Score | Reason |
|---|---|---|---|---|---|
| 1 | Normal lookup | False | 0 | 5 | The agent successfully looked up the order using the correct tool and provided an accurate, concise response matching the expected outcome. |
| 2 | Wrong order ID format | True | 0 | 5 | The agent encountered a 400 error due to an invalid order ID format, successfully recognized the correct format ('O-1002'), retried with the correct ID, and provided an accurate final answer. |
| 3 | Unknown order ID | True | 0 | 5 | The tool returned an error (400), which the agent correctly identified and handled by honestly explaining to the user without making up data or looping. |
| 4 | Auto-approved refund (under 500 rupees) | False | 0 | 5 | No errors occurred; the agent correctly checked the order and eligibility, issued the refund automatically since it was under the threshold, and accurately reported the success. |
| 5 | Refund approved by human | False | 1 | 5 | The agent correctly checked order details, eligibility, requested human approval for a refund over 500 rupees, and successfully issued and verified the refund upon approval. |
| 6 | Refund rejected by human | True | 1 | 5 | The refund was rejected by the human reviewer, and the agent correctly handled the error by stating no refund was issued, sharing the reviewer's note, and offering the requested options without retrying. |
| 7 | Large refund approved (over 5000 rupees) | True | 1 | 5 | An error/approval block was encountered because the refund exceeded 5000 rupees. The agent correctly requested human approval, received it, issued the refund, and reported the successful outcome accurately. |
| 8 | Duplicate refund attempt | False | 0 | 5 | The agent correctly identified that the order was already fully refunded and explained this clearly to the user without making any unauthorized or redundant moves. |
| 9 | Customer with many recent refunds | True | 0 | 5 | An error/flag condition occurred due to the customer's recent refund history. The agent handled it correctly by identifying the flag, refusing automatic refund, and offering to flag for manual review per policy. |
| 10 | Off-topic question | False | 0 | 5 | The agent correctly identified the off-topic question, politely refused, offered relevant assistance, and used no tools, perfectly matching the expected outcome. |

**Average score: 5.0 out of 5** (10 scenarios judged)