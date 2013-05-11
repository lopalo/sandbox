# TODO: replace it with process supervisor

# run this script from server directory

export PYTHONPATH=$PYTHONPATH:.:sulaco

python sulaco/sulaco/outer_server/message_broker.py -c configs/global.yaml &
pid_1=$!
python sulaco/sulaco/location_server/location_manager.py -c configs/global.yaml &
pid_2=$!
python frontend/main.py -p 7000 -c configs/global.yaml --debug &
pid_3=$!
python frontend/main.py -p 7001 -c configs/global.yaml --debug &
pid_4=$!
python location/main.py -pub "ipc://run/loc_1_pub" \
                        -pull "ipc://run/loc_1_pull" \
                        -ident loc_1 -c configs/global.yaml \
                        --debug &
pid_5=$!
trap 'kill $pid_1 $pid_2 $pid_3 $pid_4 $pid_5' 2 15 

python location/main.py -pub "ipc://run/loc_2_pub" \
                        -pull "ipc://run/loc_2_pull" \
                        -ident loc_2 -c configs/global.yaml \
                        --debug
