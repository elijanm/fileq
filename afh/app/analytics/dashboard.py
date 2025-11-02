# analytics/dashboard.py

class AnalyticsDashboard:
    """Query analytics data"""
    
    def __init__(self, db_handler):
        self.db = db_handler
        self.audit = db_handler.db['audit_logs']
        self.tokens = db_handler.db['token_usage']
        self.journeys = db_handler.db['user_journeys']
    
    def get_token_usage_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed token usage report"""
        pipeline = [
            {'$match': {
                'timestamp': {'$gte': start_date, '$lte': end_date},
                'type': 'ollama_request'
            }},
            {'$group': {
                '_id': {
                    'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp'}},
                    'model': '$model'
                },
                'total_requests': {'$sum': 1},
                'total_tokens': {'$sum': '$tokens_used'},
                'successful': {'$sum': {'$cond': ['$success', 1, 0]}},
                'failed': {'$sum': {'$cond': ['$success', 0, 1]}},
                'avg_duration_ms': {'$avg': '$duration_ms'}
            }},
            {'$sort': {'_id.date': -1}}
        ]
        
        results = list(self.tokens.aggregate(pipeline))
        
        return {
            'daily_breakdown': results,
            'total_tokens': sum(r['total_tokens'] for r in results),
            'total_requests': sum(r['total_requests'] for r in results),
            'avg_tokens_per_request': sum(r['total_tokens'] for r in results) / len(results) if results else 0
        }
    
    def get_conversation_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get conversation quality metrics"""
        pipeline = [
            {'$match': {
                'timestamp': {'$gte': start_date, '$lte': end_date},
                'type': 'user_action'
            }},
            {'$group': {
                '_id': '$phone',
                'total_messages': {'$sum': 1},
                'states_visited': {'$addToSet': '$state_before'},
                'completed_registration': {
                    '$sum': {'$cond': [{'$eq': ['$state_after', 'complete']}, 1, 0]}
                }
            }}
        ]
        
        results = list(self.audit.aggregate(pipeline))
        
        return {
            'total_users': len(results),
            'avg_messages_per_user': sum(r['total_messages'] for r in results) / len(results) if results else 0,
            'completion_rate': sum(r['completed_registration'] for r in results) / len(results) if results else 0
        }
    
    def get_drop_off_analysis(self) -> Dict:
        """Analyze where users drop off"""
        pipeline = [
            {'$match': {'event_type': 'drop_off'}},
            {'$group': {
                '_id': '$event_data.abandoned_at_state',
                'count': {'$sum': 1}
            }},
            {'$sort': {'count': -1}}
        ]
        
        results = list(self.journeys.aggregate(pipeline))
        
        return {
            'drop_off_points': [
                {'state': r['_id'], 'users_dropped': r['count']}
                for r in results
            ]
        }