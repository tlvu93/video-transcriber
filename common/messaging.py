import json
import logging
import os
import time
from typing import Any, Callable, Dict, Optional

import pika

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("messaging")

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

    def __init__(self, host: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the RabbitMQ client.

        Args:
            host: RabbitMQ host (defaults to environment variable RABBITMQ_HOST)
            user: RabbitMQ user (defaults to environment variable RABBITMQ_USER)
            password: RabbitMQ password (defaults to environment variable
                RABBITMQ_PASSWORD)
        """
        self.host = host or os.environ.get("RABBITMQ_HOST", "localhost")
        self.user = user or os.environ.get("RABBITMQ_USER", "guest")
        self.password = password or os.environ.get("RABBITMQ_PASSWORD", "guest")
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

        # Define exchange names
        self.event_exchange = "video_transcriber_events"

        # Connection retry settings
        self.max_retries = 3
        self.retry_delay = 5

    def connect(self) -> None:
        """
        Connect to RabbitMQ and set up the channel.
        """
        if self.connection is not None and self.connection.is_open:
            return

        for attempt in range(self.max_retries):
            try:
                # Create connection parameters with improved settings
                credentials = pika.PlainCredentials(self.user, self.password)
                parameters = pika.ConnectionParameters(
                    host=self.host,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                    # Reduce frame size to avoid frame_too_large errors
                    frame_max=131072,  # 128KB instead of default 1MB
                    # Connection timeout settings
                    connection_attempts=3,
                    retry_delay=2,
                    socket_timeout=10,
                )

                # Connect to RabbitMQ
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Declare exchanges
                self.channel.exchange_declare(exchange=self.event_exchange, exchange_type="topic", durable=True)

                logger.info(f"Connected to RabbitMQ at {self.host}")
                return

            except Exception as e:
                logger.error((f"Error connecting to RabbitMQ (attempt {attempt + 1}/" f"{self.max_retries}): {str(e)}"))
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise

    def close(self) -> None:
        """
        Close the connection to RabbitMQ.
        """
        try:
            if self.connection is not None and self.connection.is_open:
                self.connection.close()
                logger.info("Closed connection to RabbitMQ")
        except Exception as e:
            logger.error(f"Error closing RabbitMQ connection: {str(e)}")
        finally:
            self.connection = None
            self.channel = None

    def _ensure_connection(self) -> None:
        """Ensure we have a valid connection."""
        if self.connection is None or not self.connection.is_open:
            self.connect()
        assert self.connection is not None
        assert self.channel is not None

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publish an event to the event exchange.

        Args:
            event_type: Type of event (e.g., 'video.created')
            payload: Event payload as a dictionary
        """
        for attempt in range(self.max_retries):
            try:
                self._ensure_connection()

                # Limit payload size to prevent frame_too_large errors
                message = json.dumps(payload)
                if len(message) > 100000:  # 100KB limit
                    # Truncate large payloads
                    if "traceback" in payload:
                        payload["traceback"] = payload["traceback"][:1000] + "... (truncated)"
                    if "error_details" in payload and isinstance(payload["error_details"], dict):
                        if "traceback" in payload["error_details"]:
                            payload["error_details"]["traceback"] = (
                                payload["error_details"]["traceback"][:1000] + "... (truncated)"
                            )
                    message = json.dumps(payload)

                # Publish message
                self.channel.basic_publish(
                    exchange=self.event_exchange,
                    routing_key=event_type,
                    body=message,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Make message persistent
                        content_type="application/json",
                    ),
                )

                logger.info(f"Published event {event_type}")
                return

            except Exception as e:
                logger.error(
                    f"Error publishing event {event_type} (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                )
                self.close()  # Force reconnection on next attempt
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise

    def subscribe_to_event(self, event_type: str, callback: Callable, queue_name: Optional[str] = None) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Type of event to subscribe to (e.g., 'video.created')
            callback: Function to call when an event is received
            queue_name: Name of the queue to create (defaults to a generated name)
        """
        self._ensure_connection()

        try:
            # Declare queue
            if queue_name is None:
                queue_name = f"{event_type.replace('.', '_')}_queue"

            result = self.channel.queue_declare(queue=queue_name, durable=True)
            queue_name = result.method.queue

            # Bind queue to exchange
            self.channel.queue_bind(exchange=self.event_exchange, queue=queue_name, routing_key=event_type)

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
            self.channel.basic_consume(queue=queue_name, on_message_callback=message_handler)

            logger.info(f"Subscribed to event {event_type} on queue {queue_name}")

        except Exception as e:
            logger.error(f"Error subscribing to event {event_type}: {str(e)}")
            raise

    def start_consuming(self) -> None:
        """
        Start consuming messages.
        This method blocks until stop_consuming is called.
        """
        self._ensure_connection()

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
        try:
            if self.channel is not None:
                self.channel.stop_consuming()
                logger.info("Stopped consuming messages")
        except Exception as e:
            logger.error(f"Error stopping message consumption: {str(e)}")


# Helper functions for common events


def publish_video_created_event(client: RabbitMQClient, video_id: str, filename: str) -> None:
    """
    Publish a video.created event.

    Args:
        client: RabbitMQ client
        video_id: ID of the created video
        filename: Name of the video file
    """
    client.publish_event(EVENT_VIDEO_CREATED, {"video_id": video_id, "filename": filename})


def publish_transcription_created_event(client: RabbitMQClient, transcript_id: str, video_id: str) -> None:
    """
    Publish a transcription.created event.

    Args:
        client: RabbitMQ client
        transcript_id: ID of the created transcript
        video_id: ID of the video
    """
    client.publish_event(
        EVENT_TRANSCRIPTION_CREATED,
        {"transcript_id": transcript_id, "video_id": video_id},
    )


def publish_summary_created_event(client: RabbitMQClient, summary_id: str, transcript_id: str) -> None:
    """
    Publish a summary.created event.

    Args:
        client: RabbitMQ client
        summary_id: ID of the created summary
        transcript_id: ID of the transcript
    """
    client.publish_event(
        EVENT_SUMMARY_CREATED,
        {"summary_id": summary_id, "transcript_id": transcript_id},
    )


def publish_job_status_changed_event(client: RabbitMQClient, job_type: str, job_id: str, status: str) -> None:
    """
    Publish a job.status.changed event.

    Args:
        client: RabbitMQ client
        job_type: Type of job (e.g., 'transcription', 'summarization')
        job_id: ID of the job
        status: New status of the job
    """
    client.publish_event(
        EVENT_JOB_STATUS_CHANGED,
        {"job_type": job_type, "job_id": job_id, "status": status},
    )
