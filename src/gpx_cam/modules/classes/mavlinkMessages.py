import time


from pymavlink import mavutil
from ..logging import logger
from .configHandler import config

class MavlinkMessages:
    MAV_MSG_GLOBAL_POSITION_INT = {}
    REC_START_POSITION = {}
    RANGEFINDER = {}
    MAV_SATELLITES_VISIBLE = 0
    MAV_RANGEFINDER = 0

    def process_mavlink_data(*args, **kwargs):    
        try:
            # Start a connection listening to a UDP port
            the_connection = mavutil.mavlink_connection(f"udpin:0.0.0.0:{config.get('MAVPORT')}")
            # the_connection = mavutil.mavlink_connection('udpin:0.0.0.0:14445')
            # Wait for the first heartbeat 
            # This sets the system and component ID of remote system for the link
            logger.info("Waiting for heartbeat from system")
            the_connection.wait_heartbeat()
            logger.info("Heartbeat from system (system %u component %u)" % (the_connection.target_system, the_connection.target_system))

            time.sleep(1)
            # Wait for the vehicle to send GPS_RAW_INT message
            the_connection.mav.param_request_list_send(
                the_connection.target_system, the_connection.target_component
            )

            while True:

                ### Get the GLOBAL_POSITION_INT message ###
                msg = the_connection.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)
                if msg:
                    logger.debug(f"Received GLOBAL_POSITION_INT: {msg}")
                    # Convert msg to a dictionary
                    msg_dict = {
                        'time_boot_ms': msg.time_boot_ms,
                        'lat': msg.lat / 1e7,
                        'lon': msg.lon / 1e7,
                        'alt': msg.alt / 1e3,
                        'relative_alt': msg.relative_alt,
                        'vx': msg.vx / 1e2,
                        'vy': msg.vy / 1e2,
                        'vz': msg.vz / 1e2,
                        'hdg': msg.hdg / 1e3
                    }
                    mavlinkMessages.MAV_MSG_GLOBAL_POSITION_INT = msg_dict
                else:
                    logger.debug("No GLOBAL_POSITION_INT message received")

                ### Get the GPS_RAW_INT message ###
                msg = the_connection.recv_match(type='GPS_RAW_INT', blocking=True, timeout=10)
                if msg is not None:
                    mavlinkMessages.MAV_SATELLITES_VISIBLE = msg.satellites_visible
                else:
                    logger.info('No GPS_RAW_INT message received within the timeout period')

                ### Get the RANGEFINDER message ###
                msg = the_connection.recv_match(type='RANGEFINDER', blocking=True, timeout=10)
                if msg:
                    logger.debug(f"Received RANGEFINGER: {msg}")
                    mavlinkMessages.MAV_RANGEFINDER = msg.distance 
                else:
                    logger.debug("No RANGERFINDER message received")                

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            print(f"An error occurred: {e}")


mavlinkMessages = MavlinkMessages()