#include <iostream>
#include "../../include/cryptoki_ext.h"
#include "GetPinInfo.h"

using namespace std;

int main(void)
{
	CK_RV rv;
	GetPinInfo pin;
	rv = pin.Connect();
	if(CKR_OK != rv)
	{
		cout<<"Can't Connect to token"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = pin.Get();
	if(CKR_OK != rv)
	{
		cout<<"Get PIN info fault"<<endl;
		return CKR_GENERAL_ERROR;
	}else {
		cout<<"Get PIN info OK"<<endl;
		return true;
	}
}
