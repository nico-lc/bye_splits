#!/usr/bin/env bash
declare -a ITER_PARS=( $(seq 0. .1 1.) )

DRYRUN=0
REPROCESS=0
PLOT_TC=0
DO_FILLING=1
DO_SMOOTHING=1
DO_SEEDING=1
DO_CLUSTERING=1
NEVENTS=-1
declare -a SELECTIONS=( "splits_only" "above_eta_2.7" )
declare -a REGIONS=( "Si" "ECAL" "MaxShower" )
SELECTION="splits_only"
REGION="ECAL"

######################################
## Argument parsing ##################
######################################
ARGS=$(getopt -o drpf: --long dry_run,reprocess,plot_tc,no_fill,selection:,region:,iter_par:,nevents: -n "getopts_${0}" -- "$@")

#Bad arguments
if [ $? -ne 0 ];
then
  exit 1
fi
eval set -- "$ARGS"

while true; do
    case "$1" in
		--region )
			if [ -n "$2" ]; then
				if [[ ! " ${REGIONS[@]} " =~ " ${2} " ]]; then
					echo "Region ${2} is not supported."
					exit 1;
				else
					REGION="${2}";
					echo "Region to consider: ${REGION}";
				fi
			fi
			shift 2;;

		--selection )
			if [ -n "$2" ]; then
				if [[ ! " ${SELECTIONS[@]} " =~ " ${2} " ]]; then
					echo "Data selection ${2} is not supported."
					exit 1;
				else
					SELECTION="${2}";
					echo "variable to consider: ${SELECTION}";
				fi
			fi
			shift 2;;

		--no_fill )
			DO_FILLING=0;
			shift ;;

		--no_smooth )
			DO_SMOOTHING=0;
			shift ;;

		--no_seed )
			DO_SEEDING=0;
			shift ;;

		--no_cluster )
			DO_CLUSTERING=0;
			shift ;;

		-p | --plot_tc )
			PLOT_TC=1;
			shift ;;

		-r | --reprocess )
			REPROCESS=1;
			shift ;;

		-d | --dry_run )
			DRYRUN=1;
			shift ;;

		--nevents )
			NEVENTS="${2}"
			shift 2;;
		
		-- )	shift; break;;
		* ) break ;;
    esac
done

printf "===== Input Arguments =====\n"
printf "Region: %s\n" ${REGION}
printf "Selection: %s\n" ${SELECTION}
printf "Reprocess trigger cell geometry data: %s\n" ${REPROCESS}
printf "Perform filling: %s\n" ${DO_FILLING}
printf "Plot trigger cells: %s\n" ${PLOT_TC}
printf "Number of events: %s\n" ${NEVENTS}
printf "===========================\n"

if [ ${DO_FILLING} -eq 1 ]; then
	echo "Run the filling step.";
fi
if [ ${DO_SMOOTHING} -eq 1 ]; then
	echo "Run the smoothing step.";
fi
if [ ${DO_SEEDING} -eq 1 ]; then
	echo "Run the seeding step.";
fi
if [ ${DO_CLUSTERING} -eq 1 ]; then
	echo "Run the clustering step.";
fi

### Functions
function run_parallel() {
	comm="parallel -j -1 python3 iterative_optimization.py -m {} -s ${SELECTION} -n ${NEVENTS} --region ${REGION} "
	if [ ${DO_FILLING} -eq 0 ]; then
		echo "Do not run the filling step."
		comm+="--no_fill "
	fi
	if [ ${DO_SMOOTHING} -eq 0 ]; then
		echo "Do not run the smoothing step."
		comm+="--no_smooth "
	fi
	if [ ${DO_SEEDING} -eq 0 ]; then
		echo "Do not run the seeding step."
		comm+="--no_seed "
	fi
	if [ ${DO_CLUSTERING} -eq 0 ]; then
		echo "Do not run the clustering step."
		comm+="--no_cluster "
	fi

	if [ ${PLOT_TC} -eq 1 ]; then
		comm+="-p "
	fi

	comm+="$@"
	
	[[ ${DRYRUN} -eq 1 ]] && echo ${comm} || ${comm}
}

### Only one job can reprocess the data, and it has to be sequential
if [ ${REPROCESS} -eq 1 ]; then
	run_parallel -r ::: ${ITER_PARS[0]}
	run_parallel ::: ${ITER_PARS[@]:1}

else
	run_parallel ::: ${ITER_PARS[@]}
fi

echo "All jobs finished."
