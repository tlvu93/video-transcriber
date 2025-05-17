import os
import json
import logging
import pika
from typing import Dict, Any, Callable, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('messaging')

# Event types
EVENT_VIDEO_CREATED = "video.created"
EVENT_TRANSCRIPTION_CREATED = "transcription.created"
EVENT_SUMMARY_CREATED = "summary.created"
EVENT_JOB_STATUS_CHANGED = "job.status.changed"

class RabbitMQClient:
    """
    Client for interacting with RabbitMQ message broker.
    Provides methods for publishing and consuming messages.
    """
    
    def __init__(self, host: str = None, user: str = None, password: str = None):
        """
        Initialize the RabbitMQ client.
        
        Args:
            host: RabbitMQ host (defaults to environment variable RABBITMQ_HOST)
            user: RabbitMQ user (defaults to environment variable RABBITMQ_USER)
            password: RabbitMQ password (defaults to environment variable RABBITMQ_PASSWORD)
        """
        self.host = host or os.environ.get('RABBITMQ_HOST', 'localhost')
        self.user = user or os.environ.get('RABBITMQ_USER', 'guest')
        self.password = password or os.environ.get('RABBITMQ_PASSWORD', 'guest')
        self.connection = None
        self.channel = None
        
        # Define exchange names
        self.event_exchange = 'video_transcriber_events'
    
    def connect(self) -> None:
        """
        Connect to RabbitMQ and set up the channel.
        """
        if self.connection is not None and self.connection.is_open:
            return
        
        try:
            # Create connection parameters
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            # Connect to RabbitMQ
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchanges
            self.channel.exchange_declare(
                exchange=self.event_exchange,
                exchange_type='topic',
                durable=True
            )
            
            logger.info(f"Connected to RabbitMQ at {self.host}")
        
        except Exception as e:
            logger.error(f"Error connecting to RabbitMQ: {str(e)}")
            raise
    
    def close(self) -> None:
        """
        Close the connection to RabbitMQ.
        """
        if self.connection is not None and self.connection.is_open:
            self.connection.close()
            self.connection = None
            self.channel = None
            logger.info("Closed connection to RabbitMQ")
    
    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publish an event to the event exchange.
        
        Args:
            event_type: Type of event (e.g., 'video.created')
            payload: Event payload as a dictionary
        """
        if self.connection is None or not self.connection.is_open:
            self.connect()
        
        try:
            # Convert payload to JSON
            message = json.dumps(payload)
            
            # Publish message
            self.channel.basic_publish(
                exchange=self.event_exchange,
                routing_key=event_type,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info(f"Published event {event_type}: {message}")
        
        except Exception as e:
            logger.error(f"Error publishing event {event_type}: {str(e)}")
            # Try to reconnect and publish again
            self.close()
            self.connect()
            self.channel.basic_publish(
                exchange=self.event_exchange,
                routing_key=event_type,
                body=json.dumps(payload),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
    
    def subscribe_to_event(self, event_type: str, callback: Callable, queue_name: Optional[str] = None) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to (e.g., 'video.created')
            callback: Function to call when an event is received
            queue_name: Name of the queue to create (defaults to a generated name)
        """
        if self.connection is None or not self.connection.is_open:
            self.connect()
        
        try:
            # Declare queue
            if queue_name is None:
                queue_name = f"{event_type.replace('.', '_')}_queue"
            
            result = self.channel.queue_declare(queue=queue_name, durable=True)
            queue_name = result.method.queue
            
            # Bind queue to exchange
            self.channel.queue_bind(
                exchange=self.event_exchange,
                queue=queue_name,
                routing_key=event_type
            )
            
            # Set up consumer
            def message_handler(ch, method, properties, body):
                try:
                    # Parse message
                    message = json.loads(body)
                    
                    # Call callback
                    callback(message)
                    
                    # Acknowledge message
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                
                except Exception as e:
                    logger.error(f"Error handling message: {str(e)}")
                    # Reject message and requeue
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            # Set up consumer with QoS
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler
            )
            
            logger.info(f"Subscribed to event {event_type} on queue {queue_name}")
        
        except Exception as e:
            logger.error(f"Error subscribing to event {event_type}: {str(e)}")
            raise
    
    def start_consuming(self) -> None:
        """
        Start consuming messages.
        This method blocks until stop_consuming is called.
        """
        if self.connection is None or not self.connection.is_open:
            self.connect()
        
        try:
            logger.info("Starting to consume messages")
            self.channel.start_consuming()
        
        except KeyboardInterrupt:
            self.stop_consuming()
        
        except Exception as e:
            logger.error(f"Error consuming messages: {str(e)}")
            self.stop_consuming()
            raise
    
    def stop_consuming(self) -> None:
        """
        Stop consuming messages.
        """
        if self.channel is not None:
            self.channel.stop_consuming()
            logger.info("Stopped consuming messages")

# Helper functions for common events

def publish_video_created_event(client: RabbitMQClient, video_id: str, filename: str) -> None:
    """
    Publish a video.created event.
    
    Args:
        client: RabbitMQ client
        video_id: ID of the created video
        filename: Name of the video file
    """
    client.publish_event(EVENT_VIDEO_CREATED, {
        "video_id": video_id,
        "filename": filename
    })

def publish_transcription_created_event(client: RabbitMQClient, transcript_id: str, video_id: str) -> None:
    """
    Publish a transcription.created event.
    
    Args:
        client: RabbitMQ client
        transcript_id: ID of the created transcript
        video_id: ID of the video
    """
    client.publish_event(EVENT_TRANSCRIPTION_CREATED, {
        "transcript_id": transcript_id,
        "video_id": video_id
    })

def publish_summary_created_event(client: RabbitMQClient, summary_id: str, transcript_id: str) -> None:
    """
    Publish a summary.created event.
    
    Args:
        client: RabbitMQ client
        summary_id: ID of the created summary
        transcript_id: ID of the transcript
    """
    client.publish_event(EVENT_SUMMARY_CREATED, {
        "summary_id": summary_id,
        "transcript_id": transcript_id
    })

def publish_job_status_changed_event(client: RabbitMQClient, job_type: str, job_id: str, status: str) -> None:
    """
    Publish a job.status.changed event.
    
    Args:
        client: RabbitMQ client
        job_type: Type of job (e.g., 'transcription', 'summarization')
        job_id: ID of the job
        status: New status of the job
    """
    client.publish_event(EVENT_JOB_STATUS_CHANGED, {
        "job_type": job_type,
        "job_id": job_id,
        "status": status
    })
