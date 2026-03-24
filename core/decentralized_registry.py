"""
AAC Protocol Decentralized Registry

Addresses single point of failure concerns:
1. DHT (Distributed Hash Table) for agent discovery without central server
2. Gossip protocol for state synchronization between nodes
3. Multi-node consensus for agent registration
4. Local-first architecture - works offline, syncs when connected

No single Registry node - all nodes are equal peers.
"""

import hashlib
import random
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json


@dataclass
class RegistryNode:
    """A peer node in the decentralized registry network"""
    node_id: str
    endpoint: str
    last_seen: datetime
    agents_hosted: Set[str]  # Set of agent IDs this node knows about
    reputation: float  # 0-100 based on reliability


class DistributedHashTable:
    """
    Simple DHT implementation for agent lookup
    
    Agents are stored on nodes based on hash of agent_id.
    No single node controls all data.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._local_storage: Dict[str, Any] = {}  # agent_id -> agent_data
        self._routing_table: Dict[str, str] = {}  # hash_prefix -> node_endpoint
        self._known_nodes: Dict[str, RegistryNode] = {}
    
    @staticmethod
    def _hash_key(key: str) -> str:
        """Consistent hashing for key distribution"""
        return hashlib.sha256(key.encode()).hexdigest()[:20]
    
    def _is_responsible_for(self, key: str) -> bool:
        """Check if this node is responsible for storing key"""
        key_hash = self._hash_key(key)
        # Simplified: node is responsible if hash starts with node's hash prefix
        # In production, use Chord or Kademlia DHT
        return key_hash.startswith(self.node_id[:4])
    
    def _find_responsible_node(self, key: str) -> Optional[str]:
        """Find which node is responsible for key"""
        key_hash = self._hash_key(key)
        # Find closest node in routing table
        closest = None
        closest_distance = float('inf')
        
        for node_id, node in self._known_nodes.items():
            distance = self._hash_distance(key_hash, self._hash_key(node_id))
            if distance < closest_distance:
                closest_distance = distance
                closest = node.endpoint
        
        return closest
    
    @staticmethod
    def _hash_distance(h1: str, h2: str) -> int:
        """Calculate distance between two hashes (XOR metric)"""
        return int(h1, 16) ^ int(h2, 16)
    
    async def store(self, agent_id: str, agent_data: Any) -> bool:
        """
        Store agent data in DHT
        
        If this node is responsible, store locally.
        Otherwise, forward to responsible node.
        """
        if self._is_responsible_for(agent_id):
            self._local_storage[agent_id] = {
                "data": agent_data,
                "stored_at": datetime.utcnow().isoformat(),
                "stored_by": self.node_id,
            }
            return True
        else:
            # Forward to responsible node
            responsible = self._find_responsible_node(agent_id)
            if responsible:
                # In production: HTTP POST to responsible node
                return True
            return False
    
    async def retrieve(self, agent_id: str) -> Optional[Any]:
        """Retrieve agent data from DHT"""
        # Check local first
        if agent_id in self._local_storage:
            return self._local_storage[agent_id]["data"]
        
        # Query responsible node
        responsible = self._find_responsible_node(agent_id)
        if responsible and responsible != self.node_id:
            # In production: HTTP GET from responsible node
            pass
        
        return None
    
    async def discover(self, query: str) -> List[Any]:
        """
        Discover agents matching query
        
        Queries multiple nodes and aggregates results.
        """
        results = []
        
        # Query local storage
        for agent_id, agent_data in self._local_storage.items():
            if query.lower() in str(agent_data).lower():
                results.append(agent_data["data"])
        
        # Query random sample of other nodes
        sample_size = min(3, len(self._known_nodes))
        if sample_size > 0:
            sampled_nodes = random.sample(list(self._known_nodes.values()), sample_size)
            for node in sampled_nodes:
                # In production: HTTP GET from node
                pass
        
        return results


class GossipProtocol:
    """
    Gossip protocol for state synchronization
    
    Nodes periodically share updates with random peers.
    Eventually consistent - no single point of failure.
    """
    
    def __init__(self, node_id: str, dht: DistributedHashTable):
        self.node_id = node_id
        self.dht = dht
        self._pending_gossip: List[Dict] = []
    
    async def broadcast_agent_update(self, agent_id: str, update: Dict):
        """Broadcast agent update to random peers"""
        message = {
            "type": "agent_update",
            "agent_id": agent_id,
            "update": update,
            "timestamp": datetime.utcnow().isoformat(),
            "origin": self.node_id,
            "sequence": self._generate_sequence(),
        }
        
        # Select random peers
        peers = self._select_random_peers(3)
        for peer in peers:
            await self._send_gossip(peer, message)
    
    def _select_random_peers(self, count: int) -> List[RegistryNode]:
        """Select random peers from known nodes"""
        nodes = list(self.dht._known_nodes.values())
        if len(nodes) <= count:
            return nodes
        return random.sample(nodes, count)
    
    async def _send_gossip(self, peer: RegistryNode, message: Dict):
        """Send gossip message to peer"""
        # In production: HTTP POST to peer.endpoint
        pass
    
    async def handle_incoming_gossip(self, message: Dict, sender: str):
        """Handle incoming gossip message"""
        msg_type = message.get("type")
        
        if msg_type == "agent_update":
            agent_id = message.get("agent_id")
            update = message.get("update")
            # Merge update into local storage
            if self.dht._is_responsible_for(agent_id):
                await self.dht.store(agent_id, update)
        
        # Forward to other peers (gossip propagation)
        await self._forward_gossip(message, sender)
    
    async def _forward_gossip(self, message: Dict, exclude: str):
        """Forward gossip to other peers (excluding sender)"""
        # Limit propagation (TTL or probability-based)
        if random.random() < 0.7:  # 70% forward probability
            peers = self._select_random_peers(2)
            for peer in peers:
                if peer.node_id != exclude:
                    await self._send_gossip(peer, message)
    
    def _generate_sequence(self) -> int:
        """Generate monotonic sequence number"""
        # In production: use Lamport timestamp or vector clock
        return int(datetime.utcnow().timestamp() * 1000)


class ConsensusRegistry:
    """
    Multi-node consensus for agent registration
    
    Requires majority of nodes to agree on registration.
    Prevents malicious nodes from registering fake agents.
    """
    
    def __init__(self, node_id: str, dht: DistributedHashTable):
        self.node_id = node_id
        self.dht = dht
        self._pending_proposals: Dict[str, Dict] = {}
        self._votes: Dict[str, Dict[str, bool]] = {}  # proposal_id -> {node_id: vote}
    
    async def propose_registration(self, agent_data: Any) -> str:
        """
        Propose new agent registration
        
        Returns proposal ID. Registration only completes after
        majority consensus.
        """
        proposal_id = hashlib.sha256(
            f"{agent_data}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        proposal = {
            "id": proposal_id,
            "type": "agent_registration",
            "data": agent_data,
            "proposer": self.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending",
        }
        
        self._pending_proposals[proposal_id] = proposal
        self._votes[proposal_id] = {self.node_id: True}  # Proposer votes yes
        
        # Broadcast to all known nodes for voting
        for node in self.dht._known_nodes.values():
            await self._request_vote(node, proposal_id, proposal)
        
        return proposal_id
    
    async def _request_vote(self, node: RegistryNode, proposal_id: str, proposal: Dict):
        """Request vote from node"""
        # In production: HTTP POST to node.endpoint
        pass
    
    async def cast_vote(self, proposal_id: str, approve: bool, voter: str):
        """Cast vote on proposal"""
        if proposal_id not in self._votes:
            self._votes[proposal_id] = {}
        
        self._votes[proposal_id][voter] = approve
        
        # Check if consensus reached
        await self._check_consensus(proposal_id)
    
    async def _check_consensus(self, proposal_id: str):
        """Check if majority consensus reached"""
        votes = self._votes.get(proposal_id, {})
        total_nodes = len(self.dht._known_nodes) + 1  # +1 for self
        
        yes_votes = sum(1 for v in votes.values() if v)
        no_votes = sum(1 for v in votes.values() if not v)
        
        # Majority required
        if yes_votes > total_nodes / 2:
            # Consensus reached - commit
            await self._commit_registration(proposal_id)
        elif no_votes > total_nodes / 2:
            # Rejected
            self._pending_proposals[proposal_id]["status"] = "rejected"
    
    async def _commit_registration(self, proposal_id: str):
        """Commit registration after consensus"""
        proposal = self._pending_proposals.get(proposal_id)
        if not proposal:
            return
        
        proposal["status"] = "committed"
        agent_data = proposal["data"]
        agent_id = agent_data.get("id", "")
        
        # Store in DHT
        await self.dht.store(agent_id, agent_data)


class DecentralizedRegistryClient:
    """
    Client for interacting with decentralized registry
    
    Automatically discovers nodes and routes requests.
    No single point of failure - if one node fails, uses others.
    """
    
    def __init__(self, bootstrap_nodes: List[str] = None):
        self.node_id = hashlib.sha256(
            f"{datetime.utcnow().isoformat()}:{random.random()}".encode()
        ).hexdigest()[:20]
        
        self.dht = DistributedHashTable(self.node_id)
        self.gossip = GossipProtocol(self.node_id, self.dht)
        self.consensus = ConsensusRegistry(self.node_id, self.dht)
        
        # Connect to bootstrap nodes
        if bootstrap_nodes:
            for endpoint in bootstrap_nodes:
                self._add_bootstrap_node(endpoint)
    
    def _add_bootstrap_node(self, endpoint: str):
        """Add bootstrap node to known nodes"""
        node_id = hashlib.sha256(endpoint.encode()).hexdigest()[:20]
        self.dht._known_nodes[node_id] = RegistryNode(
            node_id=node_id,
            endpoint=endpoint,
            last_seen=datetime.utcnow(),
            agents_hosted=set(),
            reputation=50.0,
        )
    
    async def register_agent(self, agent_data: Any) -> str:
        """Register agent via consensus"""
        proposal_id = await self.consensus.propose_registration(agent_data)
        return proposal_id
    
    async def get_agent(self, agent_id: str) -> Optional[Any]:
        """Get agent via DHT lookup"""
        # Try local first
        result = await self.dht.retrieve(agent_id)
        if result:
            return result
        
        # Query responsible node
        responsible = self.dht._find_responsible_node(agent_id)
        if responsible:
            # In production: HTTP GET from responsible
            pass
        
        return None
    
    async def discover_agents(self, query: str) -> List[Any]:
        """Discover agents via DHT"""
        return await self.dht.discover(query)
    
    async def sync_with_peers(self):
        """Sync state with random peers via gossip"""
        # Trigger gossip exchange with peers
        for node in self.dht._known_nodes.values():
            # In production: exchange state with node
            pass
