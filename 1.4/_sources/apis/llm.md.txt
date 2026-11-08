# LLM

Language-model agents: the client, its cache, budgets, retries, providers and structured
decisions. How to use them is in [Language-model agents](../llm_agents.md).

```{eval-rst}
.. automodule:: modelly.llm
```

## Client and agents

```{eval-rst}
.. autoclass:: modelly.llm.Client
   :members:

.. autoclass:: modelly.llm.LLMAgent
   :members:

.. autofunction:: modelly.llm.decide_all
```

## Requests and replies

```{eval-rst}
.. autoclass:: modelly.llm.Request
   :members:

.. autoclass:: modelly.llm.Response
   :members:

.. autoclass:: modelly.llm.Message
   :members:
```

## Cache

```{eval-rst}
.. autoclass:: modelly.llm.ResponseCache
   :members:
```

```{eval-rst}
.. automodule:: modelly.llm.replay
   :members: replaying, active_replay
```

## Budgets and retries

```{eval-rst}
.. autoclass:: modelly.llm.Budget
   :members:

.. autoclass:: modelly.llm.Price
   :members:

.. autoclass:: modelly.llm.Usage
   :members:

.. autoclass:: modelly.llm.RetryPolicy
   :members:
```

## Providers

```{eval-rst}
.. autoclass:: modelly.llm.Provider
   :members:

.. autoclass:: modelly.llm.AnthropicProvider
   :members:

.. autoclass:: modelly.llm.OpenAICompatibleProvider
   :members:

.. autoclass:: modelly.llm.FakeProvider
   :members:
```

## Schemas

```{eval-rst}
.. autofunction:: modelly.llm.validate

.. autofunction:: modelly.llm.parse_json
```

## Errors

```{eval-rst}
.. autoexception:: modelly.llm.LLMError

.. autoexception:: modelly.llm.ProviderError

.. autoexception:: modelly.llm.CacheMiss

.. autoexception:: modelly.llm.BudgetExceeded

.. autoexception:: modelly.llm.SchemaError

.. autoexception:: modelly.llm.DecisionError
```
