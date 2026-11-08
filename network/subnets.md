# AeroParse Network Subnet Allocation Plan

## 1. Overview and Base CIDR Block
- **Supernet Allocation:** `10.20.0.0/16` (Private IPv4 Class A range)
- **Netmask:** `255.255.0.0`
- **Total Addresses in Supernet:** $2^{16} = 65,536$ addresses
- **Allocation Strategy:** Variable Length Subnet Masking (VLSM) ordered by host capacity demand (largest to smallest) starting contiguously from `10.20.0.0`.

---

## 2. Subnet Allocation Table

| Subnet Identifier | Required Hosts | Network Address | Prefix Length | Netmask | Usable Host Range | Broadcast Address | Total Usable Hosts |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`app`** | 1,000 | `10.20.0.0` | `/22` | `255.255.252.0` | `10.20.0.1` – `10.20.3.254` | `10.20.3.255` | 1,022 |
| **`public`** | 250 | `10.20.4.0` | `/24` | `255.255.255.0` | `10.20.4.1` – `10.20.4.254` | `10.20.4.255` | 254 |
| **`data`** | 100 | `10.20.5.0` | `/25` | `255.255.255.128` | `10.20.5.1` – `10.20.5.126` | `10.20.5.127` | 126 |
| **`management`** | 20 | `10.20.5.128` | `/27` | `255.255.255.224` | `10.20.5.129` – `10.20.5.158` | `10.20.5.159` | 30 |

---

## 3. Mathematical Working and Derivations

The standard formula for usable IP addresses in an IPv4 subnet of prefix length $p$ is:
$$\text{Usable Hosts} = 2^{(32 - p)} - 2$$
where the $-2$ accounts for the reserved network identifier and the directed broadcast address.

### Step 1: `app` Subnet (Demand: 1,000 hosts)
- Target requirement: $2^h - 2 \ge 1,000 \implies 2^h \ge 1,002$.
- Smallest integer exponent: $h = 10$ ($2^{10} = 1,024$).
- Prefix length: $p = 32 - 10 = 22$ (`/22`).
- Usable capacity: $1,024 - 2 = 1,022$ hosts.
- Starting boundary: `10.20.0.0`.
- Block span: 1,024 addresses $\implies$ `10.20.0.0` to `10.20.3.255`.
- Broadcast address: `10.20.3.255`.

### Step 2: `public` Subnet (Demand: 250 hosts)
- Contiguous starting boundary: immediately follows `10.20.3.255` $\implies$ `10.20.4.0`.
- Target requirement: $2^h - 2 \ge 250 \implies 2^h \ge 252$.
- Smallest integer exponent: $h = 8$ ($2^8 = 256$).
- Prefix length: $p = 32 - 8 = 24$ (`/24`).
- Usable capacity: $256 - 2 = 254$ hosts.
- Block span: 256 addresses $\implies$ `10.20.4.0` to `10.20.4.255`.
- Broadcast address: `10.20.4.255`.

### Step 3: `data` Subnet (Demand: 100 hosts)
- Contiguous starting boundary: immediately follows `10.20.4.255` $\implies$ `10.20.5.0`.
- Target requirement: $2^h - 2 \ge 100 \implies 2^h \ge 102$.
- Smallest integer exponent: $h = 7$ ($2^7 = 128$).
- Prefix length: $p = 32 - 7 = 25$ (`/25`).
- Usable capacity: $128 - 2 = 126$ hosts.
- Block span: 128 addresses $\implies$ `10.20.5.0` to `10.20.5.127`.
- Broadcast address: `10.20.5.127`.

### Step 4: `management` Subnet (Demand: 20 hosts)
- Contiguous starting boundary: immediately follows `10.20.5.127` $\implies$ `10.20.5.128`.
- Target requirement: $2^h - 2 \ge 20 \implies 2^h \ge 22$.
- Smallest integer exponent: $h = 5$ ($2^5 = 32$).
- Prefix length: $p = 32 - 5 = 27$ (`/27`).
- Usable capacity: $32 - 2 = 30$ hosts.
- Block span: 32 addresses $\implies$ `10.20.5.128` to `10.20.5.159`.
- Broadcast address: `10.20.5.159`.

---

## 4. Architectural Layout

```
10.20.0.0/16 Supernet
 ├── 10.20.0.0/22   [app]         (1022 usable hosts: 10.20.0.1 - 10.20.3.254)
 ├── 10.20.4.0/24   [public]      (254 usable hosts:  10.20.4.1 - 10.20.4.254)
 ├── 10.20.5.0/25   [data]        (126 usable hosts:  10.20.5.1 - 10.20.5.126)
 ├── 10.20.5.128/27 [management]  (30 usable hosts:   10.20.5.129 - 10.20.5.158)
 └── 10.20.5.160 ... 10.20.255.255 (Unallocated reserve capacity)
```
