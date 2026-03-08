# I-love-geekos 🦎 – Container Marketplace Demo

A demo marketplace application for **SUSECon 2026** that shows how storing
state on a **PersistentVolume** can exhaust disk space, and how switching to
**Redis** as a key-value store solves the problem.

---

## Demo story

| Phase | Storage backend | What happens |
|-------|-----------------|--------------|
| **1 – The problem** | `STORAGE_BACKEND=file` (default) | Shopping-cart data is written as JSON files to a Kubernetes **PersistentVolumeClaim**. Every visitor session creates a new file that is never cleaned up. Running the load simulator fills the volume and triggers an out-of-disk error. |
| **2 – The fix** | `STORAGE_BACKEND=redis` | One environment variable change switches the storage layer to **Redis**. Cart data is stored in-memory with automatic TTL expiry. No files, no disk pressure. |

---

## Repository layout

```
.
├── app/
│   ├── app.py              # Flask application (routes, products catalogue)
│   ├── storage.py          # Storage abstraction (FileStorage / RedisStorage)
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
│   └── redis.yaml          # Redis deployment + service (Phase 2)
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

### Phase 2 – switch to Redis (the fix)

```bash
STORAGE_BACKEND=redis docker compose --profile redis up --build
```

The app reconnects to Redis.  Open `/storage-status` – no disk pressure.

---

## Kubernetes demo (k3s / Rancher Desktop / any cluster)

### Phase 1 – deploy with file storage

```bash
# Create namespace and apply all Phase 1 manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Port-forward to access the app
kubectl port-forward svc/ilovegeekos 8080:80 -n ilovegeekos
```

Open <http://localhost:8080>.

### Trigger the out-of-disk error

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

### Phase 2 – apply the fix (Redis)

```bash
# 1. Deploy Redis
kubectl apply -f k8s/redis.yaml

# 2. Switch the storage backend (live, no rebuild required)
kubectl set env deployment/ilovegeekos STORAGE_BACKEND=redis -n ilovegeekos

# 3. Watch the rollout
kubectl rollout status deployment/ilovegeekos -n ilovegeekos
```

Open `/storage-status` again – backend is now **Redis**, disk is free.

---

## Storage abstraction (`app/storage.py`)

The key abstraction is the `create_storage()` factory:

```python
def create_storage():
    backend = os.environ.get("STORAGE_BACKEND", "file").lower()
    if backend == "redis":
        return RedisStorage()
    return FileStorage()
```

Both backends implement the same interface:

| Method | Description |
|--------|-------------|
| `get_cart(session_id)` | Return the cart as a list of item dicts |
| `save_cart(session_id, cart)` | Persist the cart |
| `clear_cart(session_id)` | Remove the cart after checkout |
| `increment_visits()` | Increment and return the global visit counter |
| `get_visits()` | Return the current visit count |
| `storage_info()` | Return a dict with backend-specific usage info |

`FileStorage` writes one JSON file per session to `DATA_DIR` (`/data`).  
`RedisStorage` stores carts under the key `cart:<session_id>` with a TTL of
3600 seconds (configurable via `CART_TTL_SECONDS`).

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