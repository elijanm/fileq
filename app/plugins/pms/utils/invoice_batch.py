from typing import List, Dict, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from plugins.pms.utils.invoice_manager import AsyncLeaseInvoiceManager
import asyncio,json
from datetime import datetime,timezone,timedelta
from functools import lru_cache
import redis.asyncio as redis

class CacheManager:
    """Redis-based caching for frequently accessed data"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl = 3600  # 1 hour
    
    async def get_property_cache(self, property_id: str) -> Optional[Dict]:
        """Get cached property data"""
        key = f"property:{property_id}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_property_cache(self, property_id: str, data: Dict):
        """Cache property data"""
        key = f"property:{property_id}"
        await self.redis.setex(key, self.ttl, json.dumps(data, default=str))
    
    async def get_tenant_balance_cache(self, tenant_id: str) -> Optional[float]:
        """Get cached tenant balance"""
        key = f"tenant:balance:{tenant_id}"
        balance = await self.redis.get(key)
        return float(balance) if balance else None
    
    async def set_tenant_balance_cache(self, tenant_id: str, balance: float):
        """Cache tenant balance"""
        key = f"tenant:balance:{tenant_id}"
        await self.redis.setex(key, 300, str(balance))  # 5 min TTL
    
    async def invalidate_tenant_cache(self, tenant_id: str):
        """Invalidate tenant cache on payment"""
        patterns = [
            f"tenant:balance:{tenant_id}",
            f"tenant:overpayment:{tenant_id}"
        ]
        for pattern in patterns:
            await self.redis.delete(pattern)
            
class BatchProcessor:
    """Process invoices in optimized batches"""
    
    def __init__(self, manager: AsyncLeaseInvoiceManager, batch_size: int = 100):
        self.manager = manager
        self.batch_size = batch_size
    
    async def process_all_leases_batched(
        self,
        billing_month: str,
        force: bool = False,
        balance_method: str = "sum"
    ) -> Dict:
        """Process leases in batches for better performance"""
        
        results = {
            "billing_period": billing_month,
            "total_leases": 0,
            "batches_processed": 0,
            "leases_processed": 0,
            "invoices_created": [],
            "errors": [],
            "processing_time": 0
        }
        
        start_time = datetime.now(timezone.utc)
        
        # Get all active leases
        cursor = self.manager.db.property_leases.find({
            "status": {"$in": ["active", "signed"]}
        })
        
        batch = []
        batch_num = 0
        
        async for lease in cursor:
            batch.append(lease)
            results["total_leases"] += 1
            
            if len(batch) >= self.batch_size:
                # Process batch
                batch_num += 1
                print(f"Processing batch {batch_num} ({len(batch)} leases)...")
                
                await self._process_batch(
                    batch, 
                    billing_month, 
                    force, 
                    balance_method,
                    results
                )
                
                results["batches_processed"] += 1
                batch = []
        
        # Process remaining leases
        if batch:
            batch_num += 1
            print(f"Processing final batch {batch_num} ({len(batch)} leases)...")
            await self._process_batch(
                batch, 
                billing_month, 
                force, 
                balance_method,
                results
            )
            results["batches_processed"] += 1
        
        end_time = datetime.now(timezone.utc)
        results["processing_time"] = (end_time - start_time).total_seconds()
        
        # Calculate performance metrics
        if results["processing_time"] > 0:
            results["leases_per_second"] = results["leases_processed"] / results["processing_time"]
            results["invoices_per_second"] = len(results["invoices_created"]) / results["processing_time"]
        
        return results
    
    async def _process_batch(
        self,
        leases: List[Dict],
        billing_month: str,
        force: bool,
        balance_method: str,
        results: Dict
    ):
        """Process a batch of leases concurrently"""
        
        # Group by property for efficient ticket creation
        leases_by_property = {}
        for lease in leases:
            property_id = lease["property_id"]
            if property_id not in leases_by_property:
                leases_by_property[property_id] = []
            leases_by_property[property_id].append(lease)
        
        # Pre-fetch all properties in this batch
        property_ids = list(leases_by_property.keys())
        properties_cursor = self.manager.db.properties.find({
            "_id": {"$in": property_ids}
        })
        properties = {p["_id"]: p async for p in properties_cursor}
        
        # Pre-fetch tenant data for balance calculation
        tenant_ids = [lease["tenant_id"] for lease in leases]
        tenants_cursor = self.manager.db.property_tenants.find({
            "_id": {"$in": tenant_ids}
        })
        tenants = {t["_id"]: t async for t in tenants_cursor}
        
        # Process each property's leases
        tasks = []
        for property_id, property_leases in leases_by_property.items():
            property_data = properties.get(property_id)
            if not property_data:
                continue
            
            task = self._process_property_leases_optimized(
                property_id,
                property_leases,
                property_data,
                billing_month,
                force,
                balance_method,
                tenants,
                results
            )
            tasks.append(task)
        
        # Execute concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_property_leases_optimized(
        self,
        property_id: str,
        leases: List[Dict],
        property_data: Dict,
        billing_month: str,
        force: bool,
        balance_method: str,
        tenants_cache: Dict,
        results: Dict
    ):
        """Optimized property lease processing with caching"""
        
        utility_tasks = []
        
        for lease in leases:
            try:
                tenant_id = str(lease["tenant_id"])
                
                # Use cached tenant data
                tenant = tenants_cache.get(tenant_id)
                
                invoice_result = await self.manager._process_single_lease(
                    lease,
                    billing_month,
                    property_data,
                    force,
                    balance_method,
                    results
                )
                
                if invoice_result and invoice_result.get("utility_tasks"):
                    utility_tasks.extend(invoice_result["utility_tasks"])
                    
            except Exception as e:
                results["errors"].append({
                    "lease_id": str(lease.get("_id")),
                    "error": str(e)
                })
        
        # Create single ticket for property
        if utility_tasks:
            ticket = await self.manager._create_property_ticket(
                property_id,
                property_data["name"],
                billing_month,
                utility_tasks,
                property_data.get("owner_id")
            )


class PerformanceMonitor:
    """Monitor and track performance metrics in real-time"""
    
    def __init__(self):
        self.metrics = {
            "total_invoices": 0,
            "total_processing_time": 0,
            "batch_times": [],
            "error_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "properties_processed": 0,
            "start_time": None,
            "end_time": None
        }
        self.property_metrics = {}  # Track per-property performance
    
    def start(self):
        """Start monitoring"""
        self.metrics["start_time"] = datetime.now(timezone.utc)
        print("🎬 Monitoring started...")
    
    def stop(self):
        """Stop monitoring"""
        self.metrics["end_time"] = datetime.now(timezone.utc)
        if self.metrics["start_time"]:
            self.metrics["total_processing_time"] = (
                self.metrics["end_time"] - self.metrics["start_time"]
            ).total_seconds()
        print("🏁 Monitoring stopped.")
    
    def record_batch(self, batch_size: int, processing_time: float, property_id: str = None):
        """Record batch processing metrics"""
        self.metrics["total_invoices"] += batch_size
        self.metrics["batch_times"].append(processing_time)
        
        if property_id:
            if property_id not in self.property_metrics:
                self.property_metrics[property_id] = {
                    "invoices": 0,
                    "processing_time": 0,
                    "batches": 0
                }
            self.property_metrics[property_id]["invoices"] += batch_size
            self.property_metrics[property_id]["processing_time"] += processing_time
            self.property_metrics[property_id]["batches"] += 1
    
    def record_property_complete(self, property_id: str, invoice_count: int):
        """Record when a property completes processing"""
        self.metrics["properties_processed"] += 1
        print(f"  ✓ Property {property_id[:8]}... completed ({invoice_count} invoices)")
    
    def record_error(self, error_type: str = "general"):
        """Record an error"""
        self.metrics["error_count"] += 1
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.metrics["cache_hits"] += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.metrics["cache_misses"] += 1
    
    def get_summary(self) -> Dict:
        """Get performance summary"""
        avg_batch_time = (
            sum(self.metrics["batch_times"]) / len(self.metrics["batch_times"])
            if self.metrics["batch_times"] else 0
        )
        
        invoices_per_second = (
            self.metrics["total_invoices"] / self.metrics["total_processing_time"]
            if self.metrics["total_processing_time"] > 0 else 0
        )
        
        cache_total = self.metrics['cache_hits'] + self.metrics['cache_misses']
        cache_hit_rate = (
            (self.metrics['cache_hits'] / cache_total * 100)
            if cache_total > 0 else 0
        )
        
        return {
            "total_invoices": self.metrics["total_invoices"],
            "properties_processed": self.metrics["properties_processed"],
            "total_time": self.metrics["total_processing_time"],
            "avg_batch_time": avg_batch_time,
            "invoices_per_second": invoices_per_second,
            "error_count": self.metrics["error_count"],
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.metrics["cache_hits"],
            "cache_misses": self.metrics["cache_misses"]
        }
    
    def print_summary(self):
        """Print detailed performance summary"""
        summary = self.get_summary()
        
        print("\n" + "=" * 80)
        print(" PERFORMANCE SUMMARY")
        print("=" * 80)
        
        print(f"\n📊 Overall Metrics:")
        print(f"   Total Invoices Created: {summary['total_invoices']:,}")
        print(f"   Properties Processed: {summary['properties_processed']:,}")
        print(f"   Total Processing Time: {summary['total_time']:.2f} seconds ({summary['total_time']/60:.1f} minutes)")
        print(f"   Average Batch Time: {summary['avg_batch_time']:.2f} seconds")
        print(f"   Throughput: {summary['invoices_per_second']:.2f} invoices/second")
        
        if summary['error_count'] > 0:
            print(f"\n⚠️  Errors:")
            print(f"   Total Errors: {summary['error_count']}")
        
        if summary['cache_hits'] + summary['cache_misses'] > 0:
            print(f"\n💾 Cache Performance:")
            print(f"   Cache Hit Rate: {summary['cache_hit_rate']:.1f}%")
            print(f"   Cache Hits: {summary['cache_hits']:,}")
            print(f"   Cache Misses: {summary['cache_misses']:,}")
        
        # Top performing properties
        if self.property_metrics:
            print(f"\n🏆 Top 5 Properties by Volume:")
            sorted_properties = sorted(
                self.property_metrics.items(),
                key=lambda x: x[1]["invoices"],
                reverse=True
            )[:5]
            
            for prop_id, metrics in sorted_properties:
                throughput = (
                    metrics["invoices"] / metrics["processing_time"]
                    if metrics["processing_time"] > 0 else 0
                )
                print(f"   {prop_id[:12]}...: {metrics['invoices']} invoices in {metrics['processing_time']:.1f}s ({throughput:.1f}/s)")
    
    def print_progress(self, current: int, total: int):
        """Print progress bar"""
        percentage = (current / total * 100) if total > 0 else 0
        bar_length = 40
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        
        elapsed = 0
        if self.metrics["start_time"]:
            elapsed = (datetime.now(timezone.utc) - self.metrics["start_time"]).total_seconds()
        
        eta = 0
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = total - current
            eta = remaining / rate if rate > 0 else 0
        
        print(f"\r   Progress: [{bar}] {percentage:.1f}% ({current}/{total}) | "
              f"Elapsed: {elapsed:.0f}s | ETA: {eta:.0f}s", end="", flush=True)


class ParallelProcessor:
    """Process multiple properties in parallel with monitoring"""
    
    def __init__(
        self, 
        manager, 
        max_workers: int = 10,
        monitor: Optional[PerformanceMonitor] = None
    ):
        self.manager = manager
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        self.monitor = monitor or PerformanceMonitor()
    
    async def process_properties_parallel(
        self,
        billing_month: str,
        force: bool = False,
        balance_method: str = "sum",
        property_ids: Optional[List[str]] = None  # Optional: process specific properties
    ) -> Dict:
        """
        Process all properties in parallel with concurrency limit.
        
        Args:
            billing_month: Billing period (e.g., "2025-11")
            force: Force regeneration of existing invoices
            balance_method: "sum" or "itemized"
            property_ids: Optional list of specific property IDs to process
        
        Returns:
            Dict with processing results
        """
        
        results = {
            "billing_period": billing_month,
            "properties_processed": 0,
            "total_invoices": 0,
            "total_leases": 0,
            "errors": [],
            "processing_time": 0,
            "invoices_by_property": {}
        }
        
        self.monitor.start()
        
        # Get all properties or specific ones
        query = {}
        if property_ids:
            query["_id"] = {"$in": property_ids}
        
        cursor = self.manager.db.properties.find(query)
        properties = await cursor.to_list(length=None)
        
        total_properties = len(properties)
        
        print(f"\n🚀 Processing {total_properties} properties in parallel")
        print(f"   Workers: {self.max_workers}")
        print(f"   Billing Period: {billing_month}")
        print(f"   Balance Method: {balance_method}")
        print()
        
        # Create tasks for each property
        tasks = []
        for i, property_data in enumerate(properties):
            task = self._process_property_with_semaphore(
                property_data,
                billing_month,
                force,
                balance_method,
                results,
                i + 1,
                total_properties
            )
            tasks.append(task)
        
        # Execute all tasks with progress tracking
        await asyncio.gather(*tasks, return_exceptions=True)
        
        print()  # New line after progress bar
        self.monitor.stop()
        
        # Calculate final metrics
        results["processing_time"] = self.monitor.metrics["total_processing_time"]
        results["total_invoices"] = self.monitor.metrics["total_invoices"]
        results["properties_processed"] = self.monitor.metrics["properties_processed"]
        
        return results
    
    async def _process_property_with_semaphore(
        self,
        property_data: Dict,
        billing_month: str,
        force: bool,
        balance_method: str,
        results: Dict,
        property_num: int,
        total_properties: int
    ):
        """Process property with concurrency limit and monitoring"""
        async with self.semaphore:
            property_start = time.time()
            
            try:
                property_id = property_data["_id"]
                property_name = property_data.get("name", "Unknown")
                
                # Update progress
                self.monitor.print_progress(property_num - 1, total_properties)
                
                # Get leases for this property
                cursor = self.manager.db.property_leases.find({
                    "property_id": property_id,
                    "status": {"$in": ["active", "signed"]}
                })
                leases = await cursor.to_list(length=None)
                
                if not leases:
                    self.monitor.record_property_complete(property_id, 0)
                    return
                
                results["total_leases"] += len(leases)
                
                # Track invoices for this property
                property_results = {
                    "billing_period": billing_month,
                    "leases_processed": 0,
                    "invoices_created": [],
                    "invoices_consolidated": [],
                    "errors": []
                }
                
                # Process leases
                await self.manager._process_property_leases(
                    property_id,
                    leases,
                    billing_month,
                    force,
                    balance_method,
                    property_results
                )
                
                # Record metrics
                invoice_count = len(property_results['invoices_created'])
                property_time = time.time() - property_start
                
                self.monitor.record_batch(
                    invoice_count, 
                    property_time, 
                    property_id
                )
                self.monitor.record_property_complete(property_id, invoice_count)
                
                # Store results
                results["invoices_by_property"][property_id] = {
                    "property_name": property_name,
                    "invoice_count": invoice_count,
                    "lease_count": len(leases),
                    "processing_time": property_time
                }
                
                # Consolidate errors
                if property_results['errors']:
                    results["errors"].extend(property_results['errors'])
                    for _ in property_results['errors']:
                        self.monitor.record_error()
                
                # Update progress
                self.monitor.print_progress(property_num, total_properties)
                
            except Exception as e:
                property_id = property_data.get("_id", "unknown")
                error_entry = {
                    "property_id": str(property_id),
                    "property_name": property_data.get("name", "Unknown"),
                    "error": str(e)
                }
                results["errors"].append(error_entry)
                self.monitor.record_error()
                print(f"\n  ✗ Error processing property {property_id}: {str(e)}")


        
async def optimized_large_scale_workflow():
    """Optimized workflow for 1M property portfolio"""
    
    # Configuration
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    print("=" * 80)
    print(" OPTIMIZED LARGE-SCALE INVOICE GENERATION")
    print(" 1,000 Properties | 100,000 Units | 90,000 Occupied")
    print("=" * 80)
    
    # Initialize optimized manager
    manager = OptimizedAsyncLeaseInvoiceManager(
        mongo_uri=mongo_uri,
        database_name=database_name,
        max_pool_size=200,
        min_pool_size=50
    )
    
    # Create indexes
    print("\n📊 Step 1: Creating database indexes...")
    db_optimizer = DatabaseOptimizer(manager.db)
    await db_optimizer.create_indexes()
    
    # Initialize cache
    print("\n💾 Step 2: Initializing cache...")
    cache = CacheManager()
    
    # Initialize processors
    batch_processor = BatchProcessor(manager, batch_size=100)
    parallel_processor = ParallelProcessor(manager, max_workers=20)
    monitor = PerformanceMonitor()
    
    billing_month = "2025-11"
    
    # Process invoices in optimized batches
    print(f"\n🚀 Step 3: Processing invoices for {billing_month}...")
    print("   Strategy: Batched processing with parallel execution")
    print("   Batch size: 100 leases")
    print("   Parallel workers: 20")
    
    start_time = datetime.now(timezone.utc)
    
    results = await batch_processor.process_all_leases_batched(
        billing_month=billing_month,
        force=False,
        balance_method="sum"  # Faster for large scale
    )
    
    end_time = datetime.now(timezone.utc)
    total_time = (end_time - start_time).total_seconds()
    
    # Display results
    print("\n" + "=" * 80)
    print(" PROCESSING COMPLETE")
    print("=" * 80)
    
    print(f"\n📈 Performance Metrics:")
    print(f"   Total Leases: {results['total_leases']:,}")
    print(f"   Leases Processed: {results['leases_processed']:,}")
    print(f"   Invoices Created: {len(results['invoices_created']):,}")
    print(f"   Batches Processed: {results['batches_processed']}")
    print(f"   Total Time: {total_time:.2f} seconds")
    print(f"   Leases/Second: {results.get('leases_per_second', 0):.2f}")
    print(f"   Invoices/Second: {results.get('invoices_per_second', 0):.2f}")
    
    if results['errors']:
        print(f"\n⚠️  Errors: {len(results['errors'])}")
        print("   First 5 errors:")
        for error in results['errors'][:5]:
            print(f"   - {error}")
    
    # Estimate for full scale
    print(f"\n🎯 Projected Full-Scale Performance:")
    if results['leases_per_second'] > 0:
        time_for_90k = 90000 / results['leases_per_second']
        print(f"   Time to process 90,000 units: {time_for_90k/60:.1f} minutes")
        print(f"   Daily capacity: {results['leases_per_second'] * 3600 * 24:,.0f} leases")
    
    # Recommendations
    print(f"\n💡 Optimization Recommendations:")
    print(f"   ✓ Use batch size: 100-200 leases")
    print(f"   ✓ Parallel workers: 20-50 (based on CPU cores)")
    print(f"   ✓ MongoDB connection pool: 200-500")
    print(f"   ✓ Enable Redis caching for property/tenant data")
    print(f"   ✓ Schedule processing during off-peak hours")
    print(f"   ✓ Use 'sum' balance method for speed")
    print(f"   ✓ Consider sharding if database > 500GB")
    
    manager.client.close()

# USAGE EXAMPLES

async def example_1_basic_parallel_processing():
    """Example 1: Basic parallel processing with monitoring"""
    
    print("=" * 80)
    print(" EXAMPLE 1: Basic Parallel Processing")
    print("=" * 80)
    
    # Initialize
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    manager = AsyncLeaseInvoiceManager(
        client,
        database_name="fq_db"
    )
    
    # Create monitor
    monitor = PerformanceMonitor()
    
    # Create parallel processor with monitor
    parallel_processor = ParallelProcessor(
        manager=manager,
        max_workers=10,  # Process 10 properties concurrently
        monitor=monitor
    )
    
    # Process all properties
    results = await parallel_processor.process_properties_parallel(
        billing_month="2025-11",
        force=False,
        balance_method="sum"
    )
    
    # Print summary
    monitor.print_summary()
    
    # Print detailed results
    print(f"\n📋 Detailed Results:")
    print(f"   Total Properties: {results['properties_processed']}")
    print(f"   Total Leases: {results['total_leases']}")
    print(f"   Total Invoices: {results['total_invoices']}")
    print(f"   Errors: {len(results['errors'])}")
    
    if results['errors']:
        print(f"\n⚠️  Error Details:")
        for error in results['errors'][:5]:  # Show first 5
            print(f"   - {error['property_name']}: {error['error']}")
    
    client.close()


async def example_2_process_specific_properties():
    """Example 2: Process specific properties only"""
    
    print("=" * 80)
    print(" EXAMPLE 2: Process Specific Properties")
    print("=" * 80)
    
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    manager = AsyncLeaseInvoiceManager(client, database_name="fq_db")
    
    monitor = PerformanceMonitor()
    parallel_processor = ParallelProcessor(manager, max_workers=5, monitor=monitor)
    
    # Get specific property IDs
    properties_cursor = manager.db.properties.find({}).limit(10)
    properties = await properties_cursor.to_list(length=None)
    property_ids = [p["_id"] for p in properties]
    
    print(f"Processing {len(property_ids)} specific properties...")
    
    # Process only these properties
    results = await parallel_processor.process_properties_parallel(
        billing_month="2025-11",
        property_ids=property_ids,
        balance_method="itemized"  # Use itemized for detailed breakdown
    )
    
    monitor.print_summary()
    
    # Show per-property breakdown
    print(f"\n📊 Per-Property Breakdown:")
    for prop_id, metrics in results['invoices_by_property'].items():
        print(f"   {metrics['property_name']}:")
        print(f"      Leases: {metrics['lease_count']}")
        print(f"      Invoices: {metrics['invoice_count']}")
        print(f"      Time: {metrics['processing_time']:.2f}s")
    
    client.close()


async def example_3_with_custom_monitoring():
    """Example 3: Custom monitoring and real-time updates"""
    
    print("=" * 80)
    print(" EXAMPLE 3: Custom Monitoring with Real-time Updates")
    print("=" * 80)
    
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    manager = AsyncLeaseInvoiceManager(client, database_name="fq_db")
    
    # Create custom monitor
    class CustomMonitor(PerformanceMonitor):
        """Custom monitor with additional tracking"""
        
        def __init__(self):
            super().__init__()
            self.milestones = [25, 50, 75, 100]
            self.milestone_idx = 0
        
        def record_property_complete(self, property_id: str, invoice_count: int):
            super().record_property_complete(property_id, invoice_count)
            
            # Check milestones
            percentage = (self.metrics["properties_processed"] / 100) * 100
            
            while (self.milestone_idx < len(self.milestones) and 
                   percentage >= self.milestones[self.milestone_idx]):
                milestone = self.milestones[self.milestone_idx]
                elapsed = (datetime.now(timezone.utc) - self.metrics["start_time"]).total_seconds()
                print(f"\n  🎯 Milestone: {milestone}% complete in {elapsed:.1f}s")
                self.milestone_idx += 1
    
    monitor = CustomMonitor()
    parallel_processor = ParallelProcessor(manager, max_workers=15, monitor=monitor)
    
    results = await parallel_processor.process_properties_parallel(
        billing_month="2025-11",
        force=False,
        balance_method="sum"
    )
    
    monitor.print_summary()
    
    client.close()


async def example_4_batch_with_parallel():
    """Example 4: Combine batch processing with parallel execution"""
    
    print("=" * 80)
    print(" EXAMPLE 4: Batch + Parallel Processing")
    print("=" * 80)
    
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    manager = AsyncLeaseInvoiceManager(client, database_name="fq_db")
    
    monitor = PerformanceMonitor()
    
    # Process in batches of properties
    properties_cursor = manager.db.properties.find({})
    all_properties = await properties_cursor.to_list(length=None)
    
    batch_size = 20  # Process 20 properties at a time
    total_batches = (len(all_properties) + batch_size - 1) // batch_size
    
    print(f"Processing {len(all_properties)} properties in {total_batches} batches")
    print(f"Batch size: {batch_size} properties")
    
    monitor.start()
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(all_properties))
        batch_properties = all_properties[start_idx:end_idx]
        property_ids = [p["_id"] for p in batch_properties]
        
        print(f"\n📦 Processing Batch {batch_num + 1}/{total_batches} ({len(property_ids)} properties)")
        
        batch_start = time.time()
        
        parallel_processor = ParallelProcessor(manager, max_workers=10, monitor=monitor)
        
        results = await parallel_processor.process_properties_parallel(
            billing_month="2025-11",
            property_ids=property_ids,
            balance_method="sum"
        )
        
        batch_time = time.time() - batch_start
        monitor.record_batch(len(property_ids), batch_time)
        
        print(f"   ✓ Batch complete: {len(property_ids)} properties in {batch_time:.2f}s")
    
    monitor.stop()
    monitor.print_summary()
    
    client.close()


async def example_5_real_world_scenario():
    """Example 5: Real-world scenario with error handling and retries"""
    
    print("=" * 80)
    print(" EXAMPLE 5: Real-World Scenario - 1000 Properties")
    print("=" * 80)
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin",
        maxPoolSize=100,  # Increased pool for parallel processing
        minPoolSize=20
    )
    manager = AsyncLeaseInvoiceManager(client, database_name="fq_db")
    
    monitor = PerformanceMonitor()
    
    # Adjust workers based on available CPU cores
    import os
    cpu_count = os.cpu_count() or 4
    max_workers = min(cpu_count * 2, 20)  # 2x CPU cores, max 20
    
    print(f"System CPUs: {cpu_count}")
    print(f"Using {max_workers} parallel workers")
    
    parallel_processor = ParallelProcessor(
        manager=manager,
        max_workers=max_workers,
        monitor=monitor
    )
    
    # Process with retries on failure
    max_retries = 3
    retry_count = 0
    success = False
    
    while retry_count < max_retries and not success:
        try:
            if retry_count > 0:
                print(f"\n🔄 Retry attempt {retry_count}/{max_retries}")
            
            results = await parallel_processor.process_properties_parallel(
                billing_month="2025-11",
                force=False,
                balance_method="sum"
            )
            
            success = True
            
            # Print comprehensive results
            monitor.print_summary()
            
            print(f"\n💼 Business Metrics:")
            print(f"   Revenue Period: {results['billing_period']}")
            print(f"   Total Invoices: {results['total_invoices']:,}")
            print(f"   Properties Billed: {results['properties_processed']:,}")
            
            # Calculate estimated revenue (assuming average rent)
            avg_rent = 10000  # KES
            estimated_revenue = results['total_invoices'] * avg_rent
            print(f"   Estimated Revenue: KES {estimated_revenue:,.2f}")
            
            # Success rate
            total_operations = results['properties_processed']
            failed_operations = len(results['errors'])
            success_rate = ((total_operations - failed_operations) / total_operations * 100) if total_operations > 0 else 0
            print(f"   Success Rate: {success_rate:.1f}%")
            
            if results['errors']:
                print(f"\n⚠️  Failed Properties ({len(results['errors'])}):")
                for error in results['errors'][:10]:
                    print(f"   - {error.get('property_name', 'Unknown')}: {error.get('error', 'Unknown error')}")
                
                if len(results['errors']) > 10:
                    print(f"   ... and {len(results['errors']) - 10} more")
            
        except Exception as e:
            retry_count += 1
            print(f"\n❌ Error occurred: {str(e)}")
            if retry_count < max_retries:
                print(f"Waiting 5 seconds before retry...")
                await asyncio.sleep(5)
            else:
                print(f"Max retries reached. Aborting.")
                monitor.print_summary()
    
    client.close()


# Main execution
async def main():
    """Run all examples"""
    
    # Choose which example to run
    examples = {
        "1": ("Basic Parallel Processing", example_1_basic_parallel_processing),
        "2": ("Specific Properties Only", example_2_process_specific_properties),
        "3": ("Custom Monitoring", example_3_with_custom_monitoring),
        "4": ("Batch + Parallel", example_4_batch_with_parallel),
        "5": ("Real-World Scenario", example_5_real_world_scenario),
    }
    
    print("\nAvailable Examples:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    
    # Run example 5 by default (most comprehensive)
    print("\nRunning Example 5: Real-World Scenario\n")
    await example_5_real_world_scenario()


if __name__ == "__main__":
    # asyncio.run(main())
    pass
    
if __name__ == "__main__":
    asyncio.run(optimized_large_scale_workflow())
    
    