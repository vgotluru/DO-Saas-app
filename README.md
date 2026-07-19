# SaaS Web App on DigitalOcean Kubernetes (DOKS)

A Flask app, containerized with Docker, deployed on DigitalOcean Kubernetes with a
public Load Balancer and CPU-based autoscaling.

## Live components

| Resource | Value |
|---|---|
| Container Registry | `registry.digitalocean.com/saasappregistry/saas-web-app` |
| DOKS cluster | `k8s-sass-web-app` (region: `sfo2`) |
| Node pool | 2 \u00d7 `s-1vcpu-2gb` |
| Namespace | `saas-app` |
| App port | `5000` |

## Repo layout

```
.
├── app.py              # Flask app: /, /healthz, /load
├── Dockerfile
├── requirements.txt
└── k8s/
    ├── 00-namespace.yaml
    ├── 01-deployment.yaml   # 2 replicas, probes on /healthz, resource requests/limits
    ├── 02-service.yaml      # type: LoadBalancer -> provisions a DO Load Balancer
    └── 03-hpa.yaml          # HPA, CPU 60%, 2-6 pods
```

## App endpoints

- `GET /` — homepage, confirms the app is reachable
- `GET /healthz` — health check used by Kubernetes probes and the DO Load Balancer
- `GET /load` — deliberately burns ~0.3s CPU per request; used to trigger the HPA during load testing

## Prerequisites

- A DigitalOcean account with billing enabled
- A DigitalOcean API token (create one under **API → Generate New Token**)
- `doctl`, `kubectl`, and `docker` available (a plain terminal, or a browser-based
  environment like GitHub Codespaces if you can't install locally)

## 1. Authenticate

```bash
doctl auth init
```
Paste your API token when prompted.

## 2. Build and push the image

```bash
doctl registry login
docker build -t registry.digitalocean.com/saasappregistry/saas-web-app:v1 .
docker push registry.digitalocean.com/saasappregistry/saas-web-app:v1
```

## 3. Create the cluster (skip if it already exists)

```bash
doctl kubernetes cluster create k8s-sass-web-app \
  --region sfo2 \
  --node-pool "name=default-pool;size=s-1vcpu-2gb;count=2"
```

## 4. Connect kubectl

```bash
doctl kubernetes cluster kubeconfig save k8s-sass-web-app
kubectl get nodes    # both nodes should show STATUS: Ready
```

## 5. Link the registry to the cluster

```bash
doctl kubernetes cluster registry add k8s-sass-web-app
```
Without this, pods fail to start with `ImagePullBackOff`.

## 6. Install metrics-server (required for autoscaling)

**DOKS does not install this by default** — skip it and the HPA sits at
`TARGETS: <unknown>/60%` forever.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# DOKS-specific: kubelet certs aren't trusted by metrics-server out of the box
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

kubectl top nodes    # once this returns real numbers, metrics are flowing
```

## 7. Deploy

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/
kubectl -n saas-app rollout status deployment/saas-web-app
```

## 8. Verify

```bash
kubectl -n saas-app get pods
kubectl -n saas-app get svc saas-web-app
```

Wait for `EXTERNAL-IP` to populate (60–90 seconds), then:

```bash
curl http://<EXTERNAL-IP>/
curl http://<EXTERNAL-IP>/healthz
```

## 9. Test autoscaling

Terminal 1 — watch the HPA live:
```bash
kubectl -n saas-app get hpa saas-web-app-hpa -w
```

Terminal 2 — generate sustained load:
```bash
kubectl -n saas-app run load-generator --rm -i --tty --restart=Never \
  --image=busybox -- /bin/sh -c \
  "while true; do wget -q -O- http://saas-web-app.saas-app.svc.cluster.local/load; done"
```

`REPLICAS` should climb within 1–2 minutes. Ctrl+C the load generator to stop;
replicas scale back down after ~5 minutes.

## Day-2 operations

**Ship a new version (zero downtime):**
```bash
docker build -t registry.digitalocean.com/saasappregistry/saas-web-app:v2 .
docker push registry.digitalocean.com/saasappregistry/saas-web-app:v2
kubectl -n saas-app set image deployment/saas-web-app \
  saas-web-app=registry.digitalocean.com/saasappregistry/saas-web-app:v2
kubectl -n saas-app rollout status deployment/saas-web-app
```

**Roll back:**
```bash
kubectl -n saas-app rollout undo deployment/saas-web-app
```

**Check logs:**
```bash
kubectl -n saas-app logs -l app=saas-web-app --tail=100 -f
```

**Tear down (avoid ongoing charges):**
```bash
kubectl delete -f k8s/          # delete the Service first — deprovisions the DO Load Balancer
doctl kubernetes cluster delete k8s-sass-web-app
doctl registry delete saasappregistry
```


## Reference documentation

- [Install and configure doctl](https://docs.digitalocean.com/reference/doctl/how-to/install/)
- [Container Registry quickstart](https://docs.digitalocean.com/products/container-registry/getting-started/quickstart/)
- [How to create Kubernetes clusters](https://docs.digitalocean.com/products/kubernetes/how-to/create-clusters/)
- [How to connect to a Kubernetes cluster](https://docs.digitalocean.com/products/kubernetes/how-to/connect-to-cluster/)
- [How to add Load Balancers to Kubernetes clusters](https://docs.digitalocean.com/products/kubernetes/how-to/add-load-balancers/)
- [Autoscale a cluster with HPA](https://docs.digitalocean.com/products/kubernetes/how-to/set-up-autoscaling/)
