# NetWatch virtual lab

Three Arista cEOS switches (one spine, two leaves) defined as code and run by
[ContainerLab](https://containerlab.dev) inside WSL2 Ubuntu.

## Prerequisites

- Native Docker engine inside WSL2 Ubuntu (`apt install docker.io docker-compose-v2`).
  Docker Desktop will NOT work: its engine lives in a separate WSL distro, so
  ContainerLab cannot reach the bridge interfaces it needs to wire links.
  The NetWatch compose stack runs on this same engine so the poller can join
  the lab network.
- ContainerLab installed in Ubuntu (`curl -sL https://containerlab.dev/setup | bash`)
- cEOS-lab image imported into the Ubuntu engine (free arista.com account for
  the download): `docker import cEOS64-lab-<version>.tar ceos:<version>`

## Bring-up

```bash
# From WSL2 Ubuntu, as root:
cd /mnt/c/Users/ronny/Projects/NetWatch
docker compose up -d --build          # NetWatch stack on the Ubuntu engine
containerlab deploy -t lab/topology.clab.yml

# Let the NetWatch poller reach the switch management network:
docker network connect netwatch-lab netwatch-poller
```

Management IPs: spine1 172.20.20.11, leaf1 .12, leaf2 .13.
SSH credentials match `.env` (`labuser`/`labpass`); eAPI is enabled for the
NAPALM/pyeapi work later in Phase 4.

## Teardown

```bash
containerlab destroy -t /mnt/c/Users/ronny/Projects/NetWatch/lab/topology.clab.yml
```

Nodes take 1-3 minutes to boot EOS; `containerlab inspect` shows state.

## WSL idle shutdown (gotcha)

WSL terminates its VM shortly after the last session closes, killing every
container. Compose services restart on the next boot (`restart: unless-stopped`)
but lab nodes do not, and their links need rewiring: rerun
`containerlab deploy --reconfigure`. Prevent it by keeping a session open
(`wsl -d Ubuntu -- sleep infinity` in a background window) or raising
`vmIdleTimeout` in `%USERPROFILE%\.wslconfig`.
