#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <unistd.h>
#include "../../include/cryptoki_ext.h"
#include "SetTimer.h"
using namespace std;

CK_RV CheckData(CK_ULONG_PTR pulTimer, char *sTemp)
{
	int i = 0;
	while(sTemp[i] != '\0')
	{
		if(!isdigit(sTemp[i]))
		{
			cout<<"1--36000 only"<<endl;
			return CKR_CANCEL;
		}
		i++;
	}
	int aTemp = 0;
	aTemp = atoi(sTemp);
	if ((aTemp < 1) || (aTemp > 36000))
	{
		cout<<"1--36000 only"<<endl;
		return CKR_CANCEL;
	}
	*pulTimer = aTemp;
	return CKR_OK;
}

int main(int argc, char** argv)
{
	CK_ULONG ulTimer;
	char cTemp[32];

	if(1 == argc)
	{
		cout<<"please input the seconds(1--36000)"<<endl;
		cin>>cTemp;
		if(!cin)
		{
			cout<<"empty input"<<endl;
			return -1;
		}
	} 
	else 
	{
		memcpy(cTemp, argv[1], sizeof(argv[1]));
	}

	CK_RV rv;
	if(strlen(cTemp) > 5)
	{
		cout<<"too long"<<endl;
		return -1;
	}
	rv = CheckData(&ulTimer, cTemp);
	if(CKR_OK != rv)
	{
		return -1;
	}
	SetTimer timer;
	rv = timer.Connect();
	if(CKR_OK != rv)
	{
		cout<<"Can't Connect to token"<<endl;
		return -1;
	}
	rv = timer.Set(ulTimer);
	if(CKR_OK != rv)
	{
		cout<<"Set timer fault"<<endl;
		return -1;
	}

	return 0;
}
