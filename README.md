# I-love-geekos 🦎 – Container Marketplace Demo

A demo marketplace application for **SUSECon 2026** that shows how storing
state on a **PersistentVolume** can exhaust disk space, and how an AI agent
can fix the problem by migrating to **Redis** as a key-value store.

---

## Demo story

| Phase | How | What happens |
|-------|-----|--------------|
| **1 – The problem** | Deploy as-is | Shopping-cart data is written as JSON files to a Kubernetes **PersistentVolumeClaim**. Every visitor session creates a new file that is never cleaned up. Running the load simulator fills the volume and triggers an out-of-disk error. |
| **2 – The fix** | AI agent writes code | Ask the AI agent to implement `RedisStorage` in `storage.py` and wire it into `create_storage()`. Redis is pre-deployed. After the code change is deployed with `STORAGE_BACKEND=redis`, no files are written and disk pressure disappears. |

---

## Repository layout

```
.
├── app/
│   ├── app.py              # Flask application (routes, products catalogue)
│   ├── storage.py          # FileStorage (Phase 1) + TODO for RedisStorage (Phase 2)
│   ├── simulate_load.py    # Script to fill the PV and trigger the error
│   ├── requirements.txt
│   ├── static/css/style.css
│   └── templates/
│       ├── base.html
│       ├── index.html         # Product listing
│       ├── product.html       # Product detail
│       ├── cart.html          # Shopping cart
│       ├── checkout.html      # Order confirmation
│       ├── storage_status.html # 💾 Live storage usage (key demo page)
│       └── 404.html
├── k8s/
│   ├── namespace.yaml
│   ├── pvc.yaml            # 50 Mi PVC (intentionally small)
│   ├── configmap.yaml      # STORAGE_BACKEND, REDIS_HOST, …
│   ├── deployment.yaml     # App deployment
│   ├── service.yaml        # ClusterIP service
│   └── redis.yaml          # Redis deployment + service (pre-deployed for Phase 2)
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Quick-start with Docker Compose

### Phase 1 – file storage (PV simulation)

```bash
docker compose up --build
```

Open <http://localhost:5000>.

Simulate load to fill the "volume":

```bash
docker compose exec app python simulate_load.py --sessions 300 --size-kb 10
```

Watch the disk fill up at <http://localhost:5000/storage-status>.

### Phase 2 – after the AI agent writes the Redis code

Once `RedisStorage` has been implemented and the image rebuilt:

```bash
STORAGE_BACKEND=redis docker compose --profile redis up --build
```

Open `/storage-status` – backend is now **Redis**, no disk pressure.

---

## Kubernetes demo (k3s / Rancher Desktop / any cluster)

### Setup – deploy everything up front

```bash
# Namespace, PVC, app, and Redis (pre-deployed, idle until Phase 2)
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/redis.yaml   # deploy Redis now; app ignores it in Phase 1

# Port-forward to access the app
kubectl port-forward svc/ilovegeekos 8080:80 -n ilovegeekos
```

Open <http://localhost:8080>.

### Trigger the out-of-disk error (Phase 1)

```bash
kubectl exec -it deploy/ilovegeekos -n ilovegeekos -- \
  python simulate_load.py --sessions 500 --size-kb 100
```

The script prints free space after every 10 sessions.  When the 50 Mi PVC is
exhausted you will see:

```
⛔  WRITE FAILED at session NNN: [Errno 28] No space left on device: '/data/cart_….json'
The volume is full – this is the error we wanted to demonstrate!
```

### Phase 2 – ask the AI agent to fix it

Give the agent this prompt (or similar):

```
The PersistentVolume is running out of disk space because every shopping cart
session writes a file that is never cleaned up.
Migrate the cart storage from the file system to Redis so we no longer need
the PersistentVolume.  The Redis service is already deployed and reachable at
host "redis" port 6379.  Use STORAGE_BACKEND=redis to activate the new backend.
```

The agent will implement `RedisStorage` in `storage.py` and update
`create_storage()`.  After it commits the change:

```bash
# Rebuild and redeploy
docker build -t ilovegeekos:latest .
kubectl rollout restart deployment/ilovegeekos -n ilovegeekos

# Activate the Redis backend
kubectl set env deployment/ilovegeekos STORAGE_BACKEND=redis -n ilovegeekos

# Watch the rollout
kubectl rollout status deployment/ilovegeekos -n ilovegeekos
```

Open `/storage-status` – backend is now **Redis**, disk is free.

---

## Storage layer (`app/storage.py`)

`FileStorage` is the only backend shipped in the repo.  It writes one JSON
file per session to `DATA_DIR` (`/data`).  The `create_storage()` factory
always returns `FileStorage` until the AI agent completes Phase 2.

The storage interface the agent must implement for `RedisStorage`:

| Method | Description |
|--------|-------------|
| `get_cart(session_id)` | Return the cart as a list of item dicts |
| `save_cart(session_id, cart)` | Persist the cart |
| `clear_cart(session_id)` | Remove the cart after checkout |
| `increment_visits()` | Increment and return the global visit counter |
| `get_visits()` | Return the current visit count |
| `storage_info()` | Return a dict with `"backend": "redis"` and memory info |

After the agent's change, `create_storage()` should return `RedisStorage()`
when `STORAGE_BACKEND=redis`.  Cart keys should expire after
`CART_TTL_SECONDS` (default 3600) seconds using Redis `SETEX`.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `file` | `file` or `redis` |
| `DATA_DIR` | `/data` | Directory for file storage (inside the container) |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |
| `CART_TTL_SECONDS` | `3600` | Redis TTL for cart keys |
| `SECRET_KEY` | `geeko-secret-change-in-prod` | Flask session secret |
| `PORT` | `5000` | HTTP port |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |

---

## License

MIT – created for demo purposes only.