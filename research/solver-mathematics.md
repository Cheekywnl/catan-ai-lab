# Catan solver: mathematics, objective, and limits

12 September 2026 · Updated through engine 0.3.2 · Four-player base game.

The target is to choose the move with the highest probability that the acting player wins, given what that player has observed. The engine now supports full-game Monte Carlo comparisons, exact dice-exposure calculations, hidden-card sampling, and explicit opening economics. These are useful components of a solver. They do not establish a game-theoretic equilibrium.

## The decision objective

For a player i, observation history h, and move a, the desired quantity is:

`Q_i(h,a) = E[1{winner = i} | h, a, opponent policies, future chance events]`.

The expectation is over plausible hidden hands and development cards, future dice and thefts, and the simulated choices of every player. The recommended move maximizes the estimated value among the candidates examined. This is a best response to the modeled opponents, not a proof of an equilibrium against arbitrary opponents.

The implemented search reconstructs a game from public board/phase information, the observer's own cards, and sampled opponent cards. It does not copy the real hidden hands, real deck order, or game RNG. At every simulated decision, the continuation policy receives that simulated player's own observation. Sampled hidden information stays inside the simulated game.

Root candidates are screened by the strategic policy, then allocated simulations with an upper-confidence-bound rule. Every candidate gets at least two samples. The code compares the sample mean plus an exploration term proportional to `sqrt(log(total samples) / candidate samples)`. This is root Monte Carlo search, not a fully expanded information-set tree or counterfactual regret minimization.

There are two distinct result types:

- **Quick/deeper search:** a simulation reaching a winner scores 1 or 0; a truncated simulation receives a bounded heuristic position value. This mixed score is not a win probability.
- **Win-objective search:** attempts long continuations. Only when every sampled continuation reaches a winner are action scores labeled simulated winning rates. The attempt cap remains explicit.

The **Estimate win chances** control runs independent sampled games and reports each player's winning fraction with a Wilson 95% sampling interval. If any games truncate, probabilities are withheld and censoring bounds are shown instead. Neither the interval nor a large number of samples corrects a wrong opponent model.

## Opening settlements: more than pips

With fair independent dice, the probability of a non-seven sum n is `(6 - abs(7-n)) / 36`. Thus a six has probability 5/36 and a two has probability 1/36. A settlement bordering a resource hex receives one card when that number is rolled; a city receives two. Pips add **expected card production**, not the chance that any income occurs.

The engine computes, for every candidate:

- Site pips and the combined expected production of both starting settlements, broken down by resource per 36 rolls.
- The probability of any income using the union of producing dice sums. Two hexes both numbered six produce together; their chances must not be counted as independent.
- Income variance from the full distribution of producing dice sums.
- Cards granted by the second opening settlement.
- Actual 4:1, generic 3:1, and resource-specific 2:1 trade access.
- A resource-flow estimate for the next settlement, city, and development card.

The fast opening policy favors shorter resource-flow times to settlements and cities, with development-card access discounted to 0.35 of that preference. This is a declared heuristic objective. It does not assert that these weights encode an optimal long-term policy. Continuation search addresses future choices explicitly.

## Turn order and contested locations

The simulator implements the exact `1,2,3,4,4,3,2,1` opening order, with a road following each settlement. The first player faces six rival settlement placements before the second pick. The fourth player has consecutive settlement picks, separated by the first settlement's road choice.

The opening audit displays the actual colors in that sequence and the current pick. Search plays the intervening settlements and roads legally; it does not assume that a desired intersection remains available. Opponent placements use the current strategic continuation policy. Their behavior is a modeling assumption, not a solved equilibrium strategy.

## Roads have destinations

For each candidate opening road, the policy adds that road to a hypothetical public board and computes reachable settlement sites. Existing own roads cost zero; an unbuilt road costs one. Opponent roads cannot be used, and opponent buildings block traversal. The distance rule removes invalid settlement sites.

The fast road evaluator searches up to three further roads and compares the economic value and resource cost of the reachable expansions. Its explanation names the target intersection and remaining road count. The bounded route horizon can miss long-term road-award tactics; full-game continuation search can compare those consequences, subject to its candidate screening and simulation budget.

## Ports must pay for themselves

Ports receive no fixed score bonus. They change resource conversion rates in the affordability calculation. At time t, the mean-flow inventory of resource r is `hand[r] + production[r] * t`. Cards needed for the target build are reserved first; only surplus cards can be converted, using the best accessible rate.

The engine finds the smallest t at which that mean-flow inventory can satisfy the target resource cost after conversion. It displays the difference with and without port access. A lumber port with no lumber income or useful lumber holdings cannot magically improve the score.

This calculation uses continuous expected resource flow. It ignores integer timing, dice variance, competing spending, robber moves, and future supply shortages. It is **not** the expected stopping time until a stochastic hand can afford a build. Its purpose is to guide and explain candidate selection; actual search continuations use legal discrete cards and trades.

## Resource tracking and robber pressure

Public production and spending update resource possibilities. Uniform hidden theft branches according to card multiplicities and preserves correlations between victim and thief. Own cards and public hand totals condition those worlds. Monopoly removes the requested resource from every other player's possible hand. Feasible trade offers/acceptances tighten minimum holdings under this engine's trade rules.

Hidden discards are strategic choices. Their likelihoods currently use a disclosed random-card approximation. Large state sets are sampled; if all particle support is lost, the display falls back to conservative intervals. Search can then sample joint inventories respecting those bounds, hand totals, and the global 19-card limit for each resource. Such samples are feasible proposals, not an exact posterior over the original history.

For a resource with one-roll production probability p, the probability of receiving it at least once over k future independent rolls on an unchanged board is `1-(1-p)^k`. Expected card income is k times the per-roll expectation. The engine derives k from turn order and whether the current turn's roll has happened, and accounts for the current robber's blocked hex.

This exposure helps explain robber pressure. The fast robber policy weights visible production and points. Selecting a robber action for continuation search additionally measures consequences for winning, including theft, subsequent income, opponents' builds, and turn order. Future board changes invalidate the fixed-board exposure calculation but are handled by each simulated continuation.

## Development cards

The starting deck composition is reduced by public plays and the observer's own known cards. Unknown opponent cards and the remaining deck are sampled jointly without replacement. The displayed chance of at least one card of a type is hypergeometric under an exchangeable-pool model. Public purchase counts and the observer's own card ages enforce play timing when reconstructing games.

Strategic retention matters: a player declining to play a card may alter a good model's belief. The current exchangeable model does not learn those choice likelihoods, so these are conditional model probabilities rather than exact psychological predictions.

## What has been measured

The final strategic policy won **85/200 games (42.5%)** against three frozen copies of the original heuristic, using all four starting seats on 50 held-out boards, seeds 2000–2049. All games completed. Resampling whole boards gives a 95% interval of **35–50%**. Source hashes, per-game winners, seeds, seats, and replay checksums are in `strength-v2.json`.

This result measures the fast strategic policy, **not** the search policy. It is not a human or external-agent benchmark. An earlier exploratory policy was tested on different boards; its result is not substituted for the final policy's evidence.

Remaining work includes opponent-population training, deeper information-set search, posterior calibration against held-out histories, search-budget ablations, and tests against strong external agents. No neural model, deep reinforcement-learning run, exploitability bound, or Nash-equilibrium certificate is claimed.

## Engine 0.3 amendment

The root candidate screen now includes the tactical policy: it calculates immediate building points, exact public road-trail lengths and award transfers, and Largest Army wins. Guaranteed wins receive priority before simulation; all opponent continuations still use the frozen strategic-v2 model. New games use corrected road-rule revision 2. Historical replay simulations retain their original rule revision and are labeled accordingly.

Both belief updates and hidden-world sampling condition resource inventories on the finite supply of 19 cards per resource. Worlds that exceed this supply are impossible and receive zero weight. If all particles are eliminated, the existing conservative-bound fallback remains explicitly approximate. These changes fix an observed negative-bank simulation failure; they do not establish a game-theoretic equilibrium.

### Equivalent acceleration in 0.3.1

For balances `b_r(t) = hand_r + production_r * t - cost_r`, affordability tests `sum(max(b_r,0)/rate_r) - sum(max(-b_r,0)) >= -1e-9`. Each balance crosses zero at most once; each segment therefore has a constant slope. The optimized adapter locates the crossing through these breakpoints, then verifies the smallest feasible point on the reference's 120/512-roll grid. The 120-roll cap and zero-time test remain unchanged. This speeds up the existing approximation; it does not turn the mean-flow estimate into a stochastic expected stopping time. Caching uses only the four input vectors, and forced actions bypass ranking. Detailed equivalence tests and timing are recorded in `speed-v3.json`.

## Public nonwin information and development cards (0.3.2)

The [official CATAN FAQ](https://www.catan.com/faq/basegame) says victory-point cards count toward winning on the player's own turn. Therefore, in a nonterminal game, a player who ended their latest turn with p visible points then had at most 9-p hidden VP cards. VP cards cannot subsequently be spent or stolen. New purchases may add new VP cards; losing an award does not retroactively change that prior bound.

Let player i hold n_i unknown cards, B_i newly bought this turn and O_i=n_i-B_i older cards. Let L_i=9-p_i be the historical old-VP cap, or leave it unrestricted without a completed-turn record. For a proposed total j_i hidden VP cards, the placement weight is

`w_i(j_i) = sum_k C(O_i, j_i-k) C(B_i, k)`, summing only feasible k with `j_i-k <= L_i`.

The current nonterminal turn owner additionally satisfies `j_i <= 9-current_visible_points`. A publicly declared winner requires enough total VP instead. With V remaining unknown VP cards and D deck positions, each joint allocation has weight `C(D, V-sum(j_i)) * product(w_i(j_i))`. Normalize over feasible allocations. There are at most five VP cards, so exact enumeration is small. Marginal expected VP and presence probabilities follow directly; non-VP card types use hypergeometric marginals conditional on each j_i. Sampling first chooses the joint allocation, then new-card VP counts k with their conditional weights, then fills non-VP slots and the deck.

This is exact counting under the stated exchangeability model and these public constraints. It does not reconstruct the entire strategic action history or model selective retention of Knights, Monopoly, or other card types. Card-age assignments must be conditioned jointly; sampling ages independently could invent playable cards. Replays reconstruct public turn records from legal actions, without changing historical event checksums.
