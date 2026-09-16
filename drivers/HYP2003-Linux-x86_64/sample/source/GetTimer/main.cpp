#include <iostream>
#include "../../include/cryptoki_ext.h"
#include "GetTimer.h"

using namespace std;

int main(void)
{
	CK_RV rv;
	GetTimer timer;
	rv = timer.Connect();
	if(CKR_OK != rv)
	{
		cout<<"Can't Connect to token"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = timer.Get();
	if(CKR_OK != rv)
	{
		cout<<"Get timer fault"<<endl;
		return CKR_GENERAL_ERROR;
	}else {
		cout<<"Get timer OK"<<endl;
		return true;
	}
}
