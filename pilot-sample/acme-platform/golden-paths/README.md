# Golden-path roots — brownfield import fixtures

Each folder here is a **Terraform root module**: a small, readable stack built
from the modules in `../modules`, wired through `module.x.y` references.

They exist to be **imported back as golden paths**. `import_golden_path` reads a
root and returns a draft path — one component per `module` block, with the edges
taken from the references the author actually declared rather than guessed by
matching names. That is the brownfield story: an organisation that already runs
Terraform gets their real stack as a governed path instead of rebuilding it.

They are deliberately **not** the `envs/` roots. Those carry backends, providers,
data sources and three environments' worth of history; these are the smallest
honest example of each shape, so what the import produced can be read at a
glance and compared against what the composer builds from the same intent.

| Root | Shape | Why it is here |
|---|---|---|
| `web-service/` | network → compute (ALB + instances) | The same shape the composer produces for "a public web service". Import it and compare: same path, two routes. |
| `eks-platform/` | network → eks → workload | The shape a plain-language EKS request got WRONG in Aug 2026 — answered with a single EC2 behind a load balancer. Importing the real thing is the counter-example. |

Both use `../../../modules/...` sources, matching `envs/`, so a reader can follow
a component straight to the module that implements it.
