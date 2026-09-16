#include <iostream>
#include "../../include/cryptoki_ext.h"
#include "SetTokenName.h"

using namespace std;

int main(int argc, char** argv)
{
	CK_RV rv;
	string str;
	if(1 == argc)
	{
		cout<<"please input the token name 1--32 char only"<<endl;
		getline(cin, str, '\n');
		if(!cin)
		{
			cout<<"empty name"<<endl;
			return CKR_GENERAL_ERROR;
		}
		if(str.length() > 32)
		{
			cout<<"too long"<<endl;
			return CKR_GENERAL_ERROR;
		}
	} 
	else 
	{
		str = argv[1];
	}

	SetTokenName token;
	rv = token.Connect();
	if(CKR_OK != rv)
	{
		cout<<"Can't Connect to token"<<endl;
		return CKR_GENERAL_ERROR;
	}
	rv = token.Set(str);
	if(CKR_OK != rv)
	{
		cout<<"Set token name fault"<<endl;
		return CKR_GENERAL_ERROR;
	}
	else 
	{
		cout<<"OK"<<endl;
		return true;
	}
}
