heu=straightline #default straightline
scene=apartment_0 # apartment_0 room_0 office_2
x=no_noise # no_noise noise
datetime=$(date +%s)
export SAVE_VIS=true #true false (when debugging)
export SLAM_SAVE_FOLDER="./data/${scene}/${heu}/${x}/${datetime}"
echo $SLAM_SAVE_FOLDER
export SCENE=$scene # changed remote locobot to use this
export HEURISTIC=$heu # changed default_behavior to use this 
export NUMTRAJ=50
echo "Using exploration heuristic ${heu}"
if [ $x == "noise" ]; then
    export NOISY_HABITAT=true
fi
# launch habitat
./droidlet/lowlevel/locobot/remote/launch_pyro_habitat.sh