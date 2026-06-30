# I3X API for Ignition

An implementation of the [CESMII i3X API](https://api.i3x.dev/v1/docs) (spec v1.0)
on top of Ignition, exposing UDT definitions and instances, their hierarchy,
live values, history, and alarm references through a single HTTP API.

The API is served by Ignition's **WebDev** module. Each endpoint resource is a
thin `doGet`/`doPost` that delegates to the project scripting library under
`i3x.*`, so the logic lives in one place.

## Layout

| Area | Path |
| --- | --- |
| Request handlers / response envelope | `i3x.handlers` |
| Ignition model (UDTs, alarms, schema) | `i3x.ignition` |
| Tag-change subscriptions | `i3x.tag` |
| Shared helpers (timestamps, cache, errors) | `i3x.utils` |
| HTTP endpoints | `com.inductiveautomation.webdev/resources/*` |

## Endpoints

`GET /info`, `GET /namespaces`, `GET|POST /objecttypes`,
`GET|POST /relationshiptypes`, `GET /objects`, `POST /objects/list`,
`POST /objects/related`, `POST /objects/value`, `POST /objects/history`,
`POST /subscriptions`, `POST /subscriptions/{register,unregister,sync,delete,list}`.

## Authentication

`/info` is intentionally public (it doubles as a health check, per the spec).
**Every other endpoint requires authentication** — `require-auth` is enabled in
each endpoint's `config.json`.

To configure who may call the API, edit the enabled handler blocks in the
WebDev resource `config.json` files (or the WebDev resource UI):

- `user-source` — the Ignition user source to authenticate against. Empty = the
  gateway default user source.
- `required-roles` — comma-separated roles. Empty = any authenticated user.
  Set this (e.g. `i3x`) to restrict access to a dedicated role.

> **TLS:** `require-https` is left `false` so the API works behind a
> TLS-terminating proxy and in local testing. For any internet-facing
> deployment, either set `require-https` to `true` on each handler or ensure TLS
> is terminated in front of the gateway — credentials are sent on every request.

## Capabilities / known limitations

`GET /info` advertises the server capabilities, which reflect what is
implemented:

- `query.history` = **true**
- `update.current` / `update.history` = **false** — write endpoints
  (`PUT /objects/value`, `PUT /objects/history`) are intentionally not
  implemented; the corresponding WebDev methods are disabled.
- `subscribe.stream` = **false** — Server-Sent Events are not supported.
  `POST /subscriptions/stream` returns `501`. Clients poll
  `POST /subscriptions/sync` instead.

## Subscriptions (polling model)

1. `POST /subscriptions` with a `clientId` → returns a `subscriptionId`.
2. `POST /subscriptions/register` with `elementIds` and optional `maxDepth`
   (1 = the element only, 0 = all composition descendants).
3. Poll `POST /subscriptions/sync`. Each call returns all pending `SyncBatch`es.
   Pass `lastSequenceNumber` to acknowledge (and drop) batches up to that point.

Updates staged between syncs and the batches awaiting acknowledgement are each
bounded (see `MAX_QUEUE_SIZE` in `i3x.tag`, default 1000). On overflow the
oldest data is dropped and `sync` responds **`206 Partial Content`** so the
client knows it missed updates and should resynchronise.

## Timestamps

All timestamps in and out of the API are **RFC 3339 UTC**
(`yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`). Parsing and formatting go through
`i3x.utils.parseUtc` / `formatUtc`, which treat values as absolute instants —
there is no gateway-timezone assumption.

## Caching

The structural model (`i3x.ignition.getUdtInstances`) browses every tag
provider, every UDT instance, and queries alarm status — too expensive to
rebuild on every request. It is cached in gateway globals for
`i3x.utils.CACHE_TTL_MS` (default **5000 ms**). Live values and history are
always read fresh; only the structure map (and last-known alarm status) is
cached. Call `i3x.utils.cacheClear()` to invalidate immediately (e.g. after
bulk UDT changes).

## Errors

Errors follow the spec `ErrorResponse` shape:

```json
{ "success": false, "responseDetail": { "title": "Not Found", "status": 404, "detail": "..." } }
```

Bulk endpoints return per-item results with the same `responseDetail` on
failures. Unexpected server errors are logged (loggers named `i3x.*`) and
returned as a generic `500` — internal details are never sent to clients.
