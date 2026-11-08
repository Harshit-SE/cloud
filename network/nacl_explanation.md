# Stateless Network ACL Design & Operational Reasoning

## 1. Stateless Traffic Filtering and Reply Rules
Network Access Control Lists (NACLs) operate at the subnet boundary as **stateless packet filters**. Unlike stateful firewalls or security groups, a stateless filter:
- Evaluates every single network packet in isolation without maintaining a connection state table (conntrack).
- Cannot correlate an incoming packet with an existing outbound TCP three-way handshake, nor an outbound packet with an existing inbound request.

When an external client initiates an inbound HTTP/S connection to the load balancer (ports 80 or 443), the inbound rule permits the ingress packet. However, when the load balancer transmits the response payload back to the client, the outbound packet is directed to the client's dynamically allocated **ephemeral port** (range 1024–65535). Because the NACL has no memory of the initial inbound request, it does not automatically permit the return packet. An explicit **outbound ephemeral allow rule** (`1024-65535` to `0.0.0.0/0`) is mandatory.

Similarly, when the load balancer forwards requests outbound to the `app` subnet on TCP port 8000, the response packets returning from the application servers arrive inbound at the load balancer's ephemeral ports. Without an explicit **inbound ephemeral allow rule** scoped to the `app` subnet CIDR (`10.20.0.0/22`), the return traffic would be dropped by the implicit default-deny rule, causing timeouts and broken connections.

---

## 2. Rule Ordering and the Evaluation Precedence for Abusive CIDRs
Stateless NACLs evaluate filtering rules sequentially in **strictly ascending numeric order** (lowest rule number first) using a **first-match-wins** termination algorithm:
- As soon as a packet matches the CIDR, protocol, and port criteria of a rule, that rule's action (`allow` or `deny`) is applied immediately, and subsequent rules are never evaluated.
- If no rule matches, the packet falls through to the terminal default deny.

Because the abusive IP range `198.51.100.0/24` represents a subset of the global internet (`0.0.0.0/0`), rule ordering is critical:
- The explicit drop rule (`action: deny`) for `198.51.100.0/24` must be assigned a lower rule number (e.g., Rule 100) than the public web allow rules for TCP 80 and TCP 443 (Rules 110 and 120).
- If the allow rules for `0.0.0.0/0` appeared earlier (e.g., Rule 90), any inbound packet from `198.51.100.0/24` targeting port 80 or 443 would match the wildcard `0.0.0.0/0` allow rule first and be permitted into the subnet, completely bypassing and nullifying the deny rule.
- Placing the specific deny rule before the broad allow rules ensures that malicious or abusive traffic is dropped unconditionally before general ingress rules are evaluated.
